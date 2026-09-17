from decimal import Decimal
from uuid import UUID
from app.db.db_enum import MatchStatus

from sqlalchemy import and_, or_, select, exists
from sqlalchemy.orm import Session, joinedload

from app.db.db_enum import BusinessStatus
from app.db.db_model import (
    Business,
    BuyerPreferences,
    Match, BuyerProfile,
)
from app.matching.config import PRICE_TOLERANCE, RERANKABLE_MATCH_STATUSES


class MatchingNotFoundError(Exception):
    """A database record required by Matching does not exist."""


class MatchingRepository:
    """
    Database access for the Matching domain.

    Responsibilities:
        - Load buyer preferences.
        - Load businesses.
        - Find candidates using hard filters.
        - Read persisted matches.
        - Add/update Match records.

    Does not:
        - Calculate FIT scores.
        - Convert ORM objects into matching schemas.
        - Decide thresholds or rankings.
        - Commit or rollback transactions.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    # ========================================================
    # BUYER
    # ========================================================
    def get_buyer_profile_by_user_id(
            self,
            user_id: UUID,
    ) -> BuyerProfile | None:
        return self.session.scalar(
            select(BuyerProfile).where(
                BuyerProfile.user_id == user_id
            )
        )

    def get_buyer_preferences(
            self,
            buyer_id: UUID,
    ) -> BuyerPreferences | None:
        return self.session.scalar(
            select(BuyerPreferences).where(
                BuyerPreferences.buyer_id == buyer_id
            )
        )

    def require_buyer_preferences(
            self,
            buyer_id: UUID,
    ) -> BuyerPreferences:
        preferences = self.get_buyer_preferences(buyer_id)

        if preferences is None:
            raise MatchingNotFoundError(
                f"Buyer preferences not found for {buyer_id}."
            )

        return preferences

    def get_recommendation_for_buyer(
            self,
            *,
            buyer_id: UUID,
            match_id: UUID,
    ) -> Match | None:
        return self.session.scalar(
            select(Match)
            .join(Match.business)
            .options(joinedload(Match.business))
            .where(
                Match.id == match_id,
                Match.buyer_id == buyer_id,
                Match.status == MatchStatus.MATCHED,
                Business.status == BusinessStatus.ACTIVE,
            )
        )

    # ========================================================
    # BUSINESS
    # ========================================================

    def get_business(
            self,
            business_id: UUID,
    ) -> Business | None:
        return self.session.scalar(
            select(Business).where(
                Business.id == business_id
            )
        )

    def require_business(
            self,
            business_id: UUID,
    ) -> Business:
        business = self.get_business(business_id)

        if business is None:
            raise MatchingNotFoundError(
                f"Business {business_id} does not exist."
            )

        return business

    # ========================================================
    # BUYER -> CANDIDATE BUSINESSES
    # ========================================================

    def get_candidate_businesses(
            self,
            preferences: BuyerPreferences,
            *,
            excluded_business_ids: set[UUID] | None = None,
    ) -> list[Business]:
        """
        Find active, matching-ready businesses satisfying
        the buyer's hard matching constraints.

        Hard filters:
            - active business
            - complete matching-required business data
            - industry
            - state/city
            - maximum purchase price + tolerance

        Intake should normally prevent incomplete businesses
        from reaching Matching. The completeness checks here
        are a defensive fallback for stale or invalid DB data.
        """

        # ----------------------------------------------------
        # ACTIVE + DEFENSIVE READINESS
        # ----------------------------------------------------

        statement = select(Business).where(
            Business.status == BusinessStatus.ACTIVE,
            Business.asking_price.is_not(None),
            Business.sde.is_not(None),
            Business.arr.is_not(None),
            Business.customer_concentration.is_not(None),
            Business.owner_involvement_hours_per_week.is_not(None),
            Business.transition_training_days.is_not(None),
            Business.deal_preference.is_not(None),
            Business.preferred_sale_timeline.is_not(None),
        )

        # ----------------------------------------------------
        # INDUSTRY
        # ----------------------------------------------------

        if preferences.target_industries:
            statement = statement.where(
                Business.industry.in_(
                    preferences.target_industries
                )
            )

        # ----------------------------------------------------
        # LOCATION
        # ----------------------------------------------------

        # Matching intentionally uses state + optional city only.
        # County is stored by Intake but is not currently a hard
        # filter to avoid over-restricting marketplace visibility.

        if preferences.target_locations:
            location_filters = []

            for location in preferences.target_locations:
                state = location.get("state")

                conditions = [
                    Business.state == state
                ]

                city = location.get("city")

                if city:
                    conditions.append(
                        Business.city == city
                    )

                location_filters.append(
                    and_(*conditions)
                )

            statement = statement.where(
                or_(*location_filters)
            )

        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        if preferences.maximum_purchase_price is not None:
            tolerance = Decimal(
                str(PRICE_TOLERANCE)
            )

            price_ceiling = (
                    preferences.maximum_purchase_price
                    * (Decimal("1") + tolerance)
            )

            statement = statement.where(
                Business.asking_price <= price_ceiling
            )

        # ----------------------------------------------------
        # EXISTING RELATIONSHIPS
        # ----------------------------------------------------

        if excluded_business_ids:
            statement = statement.where(
                Business.id.notin_(
                    excluded_business_ids
                )
            )

        return list(
            self.session.scalars(statement).all()
        )

    # ========================================================
    # BUSINESS -> CANDIDATE BUYERS
    # ========================================================

    def get_candidate_buyers(
            self,
            business: Business,
    ) -> list[BuyerPreferences]:
        """
        Find matching-ready buyers whose hard constraints
        allow the business.

        Intake should normally prevent incomplete buyer
        preferences from reaching Matching. The completeness
        checks here are a defensive fallback for stale or
        invalid DB data.
        """

        # ----------------------------------------------------
        # DEFENSIVE READINESS
        # ----------------------------------------------------

        statement = select(BuyerPreferences).where(
            BuyerPreferences.target_industries.is_not(None),
            BuyerPreferences.target_industries != [],
            BuyerPreferences.target_locations.is_not(None),
            BuyerPreferences.target_locations != [],
            BuyerPreferences.maximum_purchase_price.is_not(None),
            BuyerPreferences.minimum_required_sde.is_not(None),
            BuyerPreferences.preferred_sde.is_not(None),
            BuyerPreferences.minimum_required_arr.is_not(None),
            BuyerPreferences.preferred_arr.is_not(None),
            BuyerPreferences.preferred_owner_hours_per_week.is_not(None),
            BuyerPreferences.required_transition_training_days.is_not(None),
            BuyerPreferences.deal_preference.is_not(None),
            BuyerPreferences.accepts_customer_concentration_above_25_percent.is_not(None),
            BuyerPreferences.preferred_acquisition_timeline.is_not(None),
        )

        # ----------------------------------------------------
        # EXISTING NON-RERANKABLE RELATIONSHIPS
        # ----------------------------------------------------

        non_rerankable_match_exists = exists(
            select(Match.id).where(
                Match.buyer_id == BuyerPreferences.buyer_id,
                Match.business_id == business.id,
                Match.status.notin_(
                    RERANKABLE_MATCH_STATUSES
                ),
            )
        )

        statement = statement.where(
            ~non_rerankable_match_exists
        )

        # ----------------------------------------------------
        # INDUSTRY
        # ----------------------------------------------------

        statement = statement.where(
            BuyerPreferences.target_industries.contains(
                [business.industry]
            )
        )

        # ----------------------------------------------------
        # LOCATION
        # ----------------------------------------------------

        # County is intentionally ignored.
        #
        # A target location can match:
        #   {"state": "Texas"}
        #
        # or:
        #   {"state": "Texas", "city": "Austin"}

        location_conditions = [
            BuyerPreferences.target_locations.contains(
                [
                    {
                        "state": business.state,
                    }
                ]
            )
        ]

        if business.city:
            location_conditions.append(
                BuyerPreferences.target_locations.contains(
                    [
                        {
                            "state": business.state,
                            "city": business.city,
                        }
                    ]
                )
            )

        statement = statement.where(
            or_(*location_conditions)
        )

        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        if business.asking_price is not None:
            tolerance = Decimal(
                str(PRICE_TOLERANCE)
            )

            minimum_budget = (
                    business.asking_price
                    / (Decimal("1") + tolerance)
            )

            statement = statement.where(
                BuyerPreferences.maximum_purchase_price
                >= minimum_budget
            )

        return list(
            self.session.scalars(statement).all()
        )
    # ========================================================
    # MATCH LOOKUP
    # ========================================================

    def get_match(
            self,
            *,
            buyer_id: UUID,
            business_id: UUID,
    ) -> Match | None:
        return self.session.scalar(
            select(Match).where(
                Match.buyer_id == buyer_id,
                Match.business_id == business_id,
            )
        )

    def list_matches_for_buyer(
            self,
            *,
            buyer_id: UUID,
            limit: int,
            offset: int,
    ) -> list[Match]:
        """
        Return persisted matches for a buyer ordered by FIT score.

        One extra row is requested so the API can determine
        whether another page exists.
        """

        statement = (
            select(Match)
            .where(
                Match.buyer_id == buyer_id,
            )
            .order_by(
                Match.score.desc(),
                Match.id.asc(),
            )
            .limit(limit + 1)
            .offset(offset)
        )

        return list(
            self.session.scalars(statement).all()
        )

    def list_recommendations_for_buyer(
            self,
            *,
            buyer_id: UUID,
            limit: int,
            offset: int,
    ) -> list[Match]:
        statement = (
            select(Match)
            .join(Match.business)
            .options(joinedload(Match.business))
            .where(
                Match.buyer_id == buyer_id,
                Match.status == MatchStatus.MATCHED,
                Business.status == BusinessStatus.ACTIVE,
            )
            .order_by(
                Match.score.desc(),
                Match.id.asc(),
            )
            .limit(limit + 1)
            .offset(offset)
        )

        return list(
            self.session.scalars(statement).all()
        )

    def list_matches_for_business(
            self,
            *,
            business_id: UUID,
            limit: int,
            offset: int,
    ) -> list[Match]:
        """
        Return persisted matches for a business ordered by FIT score.

        One extra row is requested so the API can determine
        whether another page exists.
        """

        statement = (
            select(Match)
            .where(
                Match.business_id == business_id,
            )
            .order_by(
                Match.score.desc(),
                Match.id.asc(),
            )
            .limit(limit + 1)
            .offset(offset)
        )

        return list(
            self.session.scalars(statement).all()
        )

    # ========================================================
    # MATCH PERSISTENCE
    # ========================================================

    def add_match(
            self,
            match: Match,
    ) -> Match:
        """
        Stage a new Match for persistence.

        Transaction ownership remains with the service/task.
        """

        self.session.add(match)
        self.session.flush()

        return match

    def delete_match(
            self,
            match: Match,
    ) -> None:
        """
        Remove a Match that is no longer valid.

        Flushes the change but does not commit.
        """

        self.session.delete(match)
        self.session.flush()

    # ========================================================
    # MATCH PERSISTENCE
    # ========================================================
    def list_rerankable_matches_for_buyer(
            self,
            buyer_id: UUID,
    ) -> list[Match]:
        return list(
            self.session.scalars(
                select(Match).where(
                    Match.buyer_id == buyer_id,
                    Match.status.in_(RERANKABLE_MATCH_STATUSES),
                )
            ).all()
        )

    def get_non_rerankable_business_ids_for_buyer(
            self,
            buyer_id: UUID,
    ) -> set[UUID]:
        """
        Return businesses that already have a relationship with
        this buyer which the matching engine does not own.

        Only MATCHED relationships may participate in reranking.
        """

        return set(
            self.session.scalars(
                select(Match.business_id).where(
                    Match.buyer_id == buyer_id,
                    Match.status.notin_(RERANKABLE_MATCH_STATUSES),
                )
            ).all()
        )

    def get_match_by_id(
            self,
            match_id: UUID,
    ) -> Match | None:

        return self.session.scalar(
            select(Match).where(
                Match.id == match_id
            )
        )



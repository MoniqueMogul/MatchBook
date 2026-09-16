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
from app.matching.config import PRICE_TOLERANCE


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
            .options(joinedload(Match.business))
            .where(
                Match.id == match_id,
                Match.buyer_id == buyer_id,
                Match.status == MatchStatus.MATCHED,
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
        Find active businesses satisfying the buyer's hard
        matching constraints.

        Hard filters:
            - active business
            - industry, when specified
            - state/city, when specified
            - maximum purchase price + tolerance, when specified
        """

        statement = select(Business).where(
            Business.status == BusinessStatus.ACTIVE
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

        if preferences.target_locations:
            location_filters = []

            for location in preferences.target_locations:
                state = location.get("state")

                # State is required by Intake.
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
                Business.asking_price.is_not(None),
                Business.asking_price <= price_ceiling,
            )

            if excluded_business_ids:
                statement = statement.where(
                    Business.id.notin_(excluded_business_ids)
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
        Find buyers whose hard constraints allow the business.

        None / empty preference means the buyer does not care
        about that dimension.
        """

        statement = select(BuyerPreferences)

        # ----------------------------------------------------
        # EXISTING NON-RERANKABLE RELATIONSHIPS
        # ----------------------------------------------------

        non_rerankable_match_exists = exists(
            select(Match.id).where(
                Match.buyer_id == BuyerPreferences.buyer_id,
                Match.business_id == business.id,
                Match.status != MatchStatus.MATCHED,
            )
        )

        statement = statement.where(
            ~non_rerankable_match_exists
        )

        # ----------------------------------------------------
        # INDUSTRY
        # ----------------------------------------------------

        statement = statement.where(
            or_(
                BuyerPreferences.target_industries.is_(None),
                BuyerPreferences.target_industries == [],
                BuyerPreferences.target_industries.contains(
                    [business.industry]
                ),
            )
        )

        # ----------------------------------------------------
        # LOCATION
        # ----------------------------------------------------

        location_conditions = [
            BuyerPreferences.target_locations.is_(None),
            BuyerPreferences.target_locations == [],
        ]

        # Buyer accepts anywhere in this state.
        location_conditions.append(
            BuyerPreferences.target_locations.contains(
                [
                    {
                        "state": business.state,
                    }
                ]
            )
        )

        # Buyer specifically accepts this city.
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
                or_(
                    BuyerPreferences.maximum_purchase_price.is_(None),
                    BuyerPreferences.maximum_purchase_price
                    >= minimum_budget,
                )
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
            .options(joinedload(Match.business))
            .where(
                Match.buyer_id == buyer_id,
                Match.status == MatchStatus.MATCHED,
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
        """
        Return recommendations currently controlled by
        the matching engine.
        """

        return list(
            self.session.scalars(
                select(Match).where(
                    Match.buyer_id == buyer_id,
                    Match.status == MatchStatus.MATCHED,
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
                    Match.status != MatchStatus.MATCHED,
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
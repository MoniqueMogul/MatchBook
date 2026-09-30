"""Add user and business profile image keys."""
from alembic import op
import sqlalchemy as sa

revision = 'f37c9021ab41'
down_revision = '0eadaaa48810'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('profile_image_key', sa.String(500), nullable=True))
    op.add_column('businesses', sa.Column('profile_image_key', sa.String(500), nullable=True))


def downgrade():
    op.drop_column('businesses', 'profile_image_key')
    op.drop_column('users', 'profile_image_key')

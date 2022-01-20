"""Add export_settings column

Revision ID: 259f90f13bd6
Revises: 2b468eeb193d
Create Date: 2021-10-04 12:29:35.298536

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "259f90f13bd6"
down_revision = "2b468eeb193d"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "configuration",
        sa.Column(
            "export_settings",
            sa.JSON(),
            server_default='{"include_labels": true, "remove_group_name": true, "do_not_split_select_multiple": false, "include_reviews": false, "include_labels_only": true, "value_select_multiples": true}',
            nullable=False,
        ),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("configuration", "export_settings")
    # ### end Alembic commands ###
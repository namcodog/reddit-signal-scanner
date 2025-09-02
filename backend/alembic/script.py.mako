"""${message}

迁移ID: ${up_revision}
基于版本: ${down_revision | comma,n}
创建时间: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    """执行数据库升级操作"""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """执行数据库降级操作"""
    ${downgrades if downgrades else "pass"}
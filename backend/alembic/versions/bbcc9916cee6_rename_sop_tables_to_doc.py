"""rename sop tables to doc

Revision ID: bbcc9916cee6
Revises: 8572659ab138
Create Date: 2026-09-27 12:09:08.769509

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'bbcc9916cee6'
down_revision: Union[str, None] = '8572659ab138'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Pure rename — "SOP" was confusing to product users ("Doc"/"Documentation"
    # reads clearer). op.rename_table preserves all existing rows; no data loss.
    op.rename_table('sop_jobs', 'doc_jobs')
    op.rename_table('sop_documents', 'doc_documents')
    op.rename_table('sop_events', 'doc_events')
    op.execute('ALTER INDEX ix_sop_events_created_at RENAME TO ix_doc_events_created_at')
    op.execute('ALTER INDEX ix_sop_events_job_id RENAME TO ix_doc_events_job_id')


def downgrade() -> None:
    op.execute('ALTER INDEX ix_doc_events_job_id RENAME TO ix_sop_events_job_id')
    op.execute('ALTER INDEX ix_doc_events_created_at RENAME TO ix_sop_events_created_at')
    op.rename_table('doc_events', 'sop_events')
    op.rename_table('doc_documents', 'sop_documents')
    op.rename_table('doc_jobs', 'sop_jobs')

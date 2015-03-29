"""empty message

Revision ID: 1871b0bae8bf
Revises: None
Create Date: 2015-03-07 19:06:51.455453

"""

# revision identifiers, used by Alembic.
revision = '1871b0bae8bf'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('database',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('display_name', sa.String(length=255), nullable=True),
    sa.Column('description', sa.String(length=2048), nullable=True),
    sa.Column('number_of_organisms', sa.Integer(), nullable=True),
    sa.Column('number_of_phams', sa.Integer(), nullable=True),
    sa.Column('created', sa.DateTime(), nullable=True),
    sa.Column('modified', sa.DateTime(), nullable=True),
    sa.Column('locked', sa.Boolean(), nullable=True),
    sa.Column('visible', sa.Boolean(), nullable=True),
    sa.Column('cdd_search', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_database_display_name'), 'database', ['display_name'], unique=True)
    op.create_table('job',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('database_id', sa.Integer(), nullable=True),
    sa.Column('database_name', sa.String(length=255), nullable=True),
    sa.Column('status_code', sa.String(length=32), nullable=True),
    sa.Column('status_message', sa.String(length=255), nullable=True),
    sa.Column('modified', sa.DateTime(), nullable=True),
    sa.Column('start_time', sa.DateTime(), nullable=True),
    sa.Column('runtime', sa.Interval(), nullable=True),
    sa.Column('seen', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['database_id'], ['database.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('genbank_file',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.Integer(), nullable=True),
    sa.Column('filename', sa.String(length=2048), nullable=True),
    sa.Column('phage_name', sa.String(length=255), nullable=True),
    sa.Column('length', sa.Integer(), nullable=True),
    sa.Column('genes', sa.Integer(), nullable=True),
    sa.Column('gc_content', sa.Float(), nullable=True),
    sa.Column('expires', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['job_id'], ['job.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('job_organism_to_delete',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('organism_id', sa.String(length=255), nullable=True),
    sa.Column('job_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['job_id'], ['job.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('job_organism_to_delete')
    op.drop_table('genbank_file')
    op.drop_table('job')
    op.drop_index(op.f('ix_database_display_name'), table_name='database')
    op.drop_table('database')
    ### end Alembic commands ###

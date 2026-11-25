from django.db import migrations


COMPANY_DOCUMENT_LOCK = [
    """
    CREATE OR REPLACE FUNCTION documents_companydocument_active_lock()
    RETURNS trigger AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            IF OLD.status = 'ACTIVE' THEN
                RAISE EXCEPTION USING MESSAGE =
                    'Active document ' || OLD.id || ' is locked and cannot be deleted';
            END IF;
            RETURN OLD;
        END IF;

        -- Status changes (e.g. revoking a certificate) and detaching the
        -- document type (used when a DocumentType is deleted) stay allowed.
        -- Everything that defines the certificate content is frozen.
        IF OLD.status = 'ACTIVE' AND (
            NEW.company_id IS DISTINCT FROM OLD.company_id OR
            NEW.recipient IS DISTINCT FROM OLD.recipient OR
            NEW.issued_date IS DISTINCT FROM OLD.issued_date OR
            NEW.expiry_date IS DISTINCT FROM OLD.expiry_date OR
            NEW.never_expires IS DISTINCT FROM OLD.never_expires OR
            NEW.template_id IS DISTINCT FROM OLD.template_id OR
            NEW.uuid IS DISTINCT FROM OLD.uuid
        ) THEN
            RAISE EXCEPTION USING MESSAGE =
                'Active document ' || OLD.id || ' is locked and can only change status';
        END IF;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """,
    "DROP TRIGGER IF EXISTS documents_companydocument_active_lock ON documents_companydocument;",
    """
    CREATE TRIGGER documents_companydocument_active_lock
    BEFORE UPDATE OR DELETE ON documents_companydocument
    FOR EACH ROW EXECUTE FUNCTION documents_companydocument_active_lock();
    """,
]

DOCUMENT_FIELD_LOCK = [
    """
    CREATE OR REPLACE FUNCTION documents_documentfield_active_lock()
    RETURNS trigger AS $$
    DECLARE
        parent_id bigint;
        parent_status varchar(20);
    BEGIN
        IF TG_OP = 'DELETE' THEN
            parent_id := OLD.document_id;
        ELSE
            parent_id := NEW.document_id;
        END IF;

        SELECT status INTO parent_status
        FROM documents_companydocument
        WHERE id = parent_id;

        IF parent_status = 'ACTIVE' THEN
            RAISE EXCEPTION USING MESSAGE =
                'Document ' || parent_id || ' is ACTIVE and its fields are locked';
        END IF;

        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """,
    "DROP TRIGGER IF EXISTS documents_documentfield_active_lock ON documents_documentfield;",
    """
    CREATE TRIGGER documents_documentfield_active_lock
    BEFORE UPDATE OR DELETE ON documents_documentfield
    FOR EACH ROW EXECUTE FUNCTION documents_documentfield_active_lock();
    """,
]

REVERSE = [
    "DROP TRIGGER IF EXISTS documents_documentfield_active_lock ON documents_documentfield;",
    "DROP FUNCTION IF EXISTS documents_documentfield_active_lock();",
    "DROP TRIGGER IF EXISTS documents_companydocument_active_lock ON documents_companydocument;",
    "DROP FUNCTION IF EXISTS documents_companydocument_active_lock();",
]


def _run(schema_editor, statements):
    # Only PostgreSQL supports these triggers. SQLite (used by local tests)
    # simply skips them and relies on the API guards.
    if schema_editor.connection.vendor != "postgresql":
        return
    for statement in statements:
        schema_editor.execute(statement)


def create_locks(apps, schema_editor):
    _run(schema_editor, COMPANY_DOCUMENT_LOCK + DOCUMENT_FIELD_LOCK)


def drop_locks(apps, schema_editor):
    _run(schema_editor, REVERSE)


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0011_alter_companydocument_document_type'),
    ]

    operations = [
        migrations.RunPython(create_locks, drop_locks),
    ]

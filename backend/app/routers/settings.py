import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.database import get_db
from app.models.entities import BrokerAccount
from app.schemas.settings import BrokerAccountUpsertRequest
from app.services.audit import log_event
from app.services.secrets import decrypt_json, encrypt_json, fingerprint

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/broker-accounts")
def list_broker_accounts(db: Session = Depends(get_db), _: str = Depends(require_roles("admin", "trader"))):
    rows = db.scalars(select(BrokerAccount).order_by(BrokerAccount.id.desc())).all()
    return {
        "items": [
            {
                "id": r.id,
                "provider": r.provider,
                "environment": r.environment,
                "account_ref": r.account_ref,
                "credentials_fingerprint": r.credentials_fingerprint,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }


@router.post("/broker-accounts")
def upsert_broker_account(
    payload: BrokerAccountUpsertRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin")),
):
    existing = db.scalar(
        select(BrokerAccount).where(
            BrokerAccount.provider == payload.provider,
            BrokerAccount.environment == payload.environment,
        )
    )

    encrypted = encrypt_json(json.dumps(payload.credentials))
    fp = fingerprint(json.dumps(payload.credentials, sort_keys=True))

    if not existing:
        existing = BrokerAccount(
            provider=payload.provider,
            environment=payload.environment,
            account_ref=payload.account_ref,
            encrypted_credentials=encrypted,
            credentials_fingerprint=fp,
        )
    else:
        existing.account_ref = payload.account_ref
        existing.encrypted_credentials = encrypted
        existing.credentials_fingerprint = fp

    db.add(existing)
    db.commit()
    db.refresh(existing)

    log_event(
        db,
        "BROKER_ACCOUNT_UPSERT",
        {"provider": existing.provider, "environment": existing.environment, "account_ref": existing.account_ref},
    )

    return {
        "id": existing.id,
        "provider": existing.provider,
        "environment": existing.environment,
        "account_ref": existing.account_ref,
        "credentials_fingerprint": existing.credentials_fingerprint,
        "created_at": existing.created_at,
    }


@router.get("/broker-accounts/{account_id}/credentials")
def get_broker_credentials(
    account_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin")),
):
    row = db.scalar(select(BrokerAccount).where(BrokerAccount.id == account_id))
    if not row:
        raise HTTPException(status_code=404, detail="Broker account not found")
    return {
        "id": row.id,
        "provider": row.provider,
        "environment": row.environment,
        "credentials": json.loads(decrypt_json(row.encrypted_credentials)),
    }

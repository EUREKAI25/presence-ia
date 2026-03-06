"""Routes: /social/accounts + /social/posts"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import (
    db_create_social_account, db_create_social_post, db_get_social_account,
    db_get_social_post, db_list_social_accounts, db_list_social_posts,
    db_update_social_account, db_update_social_post, get_db,
)
from ...models import EurkaiOutput, SocialAccountCreate, SocialPostCreate, SocialPostStatus

router = APIRouter(prefix="/social", tags=["Social"])


@router.post("/accounts", response_model=EurkaiOutput)
def create_account(payload: SocialAccountCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["credentials_enc"] = data.pop("credentials", {})
    obj = db_create_social_account(db, data)
    return EurkaiOutput(success=True, result={"id": obj.id, "platform": obj.platform,
                                               "account_name": obj.account_name}, message="Account created")

@router.get("/accounts", response_model=EurkaiOutput)
def list_accounts(project_id: str, platform: Optional[str] = None, db: Session = Depends(get_db)):
    rows = db_list_social_accounts(db, project_id, platform=platform)
    return EurkaiOutput(success=True, result=[
        {"id": r.id, "platform": r.platform, "account_name": r.account_name,
         "daily_post_limit": r.daily_post_limit, "posted_today": r.posted_today}
        for r in rows
    ], message="OK")

@router.post("/posts", response_model=EurkaiOutput)
def create_post(payload: SocialPostCreate, db: Session = Depends(get_db)):
    if not db_get_social_account(db, payload.account_id):
        raise HTTPException(404, "Social account not found")
    obj = db_create_social_post(db, payload.model_dump())
    return EurkaiOutput(success=True, result={"id": obj.id, "status": obj.status}, message="Post created")

@router.get("/posts", response_model=EurkaiOutput)
def list_posts(project_id: str, account_id: Optional[str] = None,
               status: Optional[str] = None, db: Session = Depends(get_db)):
    rows = db_list_social_posts(db, project_id, account_id=account_id, status=status)
    return EurkaiOutput(success=True, result=[
        {"id": r.id, "platform": r.platform, "status": r.status,
         "scheduled_at": r.scheduled_at.isoformat() if r.scheduled_at else None,
         "published_at": r.published_at.isoformat() if r.published_at else None,
         "external_url": r.external_url}
        for r in rows
    ], message="OK")

@router.post("/posts/{post_id}/publish", response_model=EurkaiOutput)
def publish_post(post_id: str, db: Session = Depends(get_db)):
    """Trigger immediate publish via the configured provider for this account."""
    post = db_get_social_post(db, post_id)
    if not post: raise HTTPException(404, "Post not found")
    account = db_get_social_account(db, post.account_id)
    if not account: raise HTTPException(404, "Account not found")

    try:
        from datetime import datetime
        if account.platform == "instagram":
            from ...channels.social.providers.instagram import InstagramProvider
            creds = account.credentials_enc or {}
            provider = InstagramProvider(access_token=creds.get("access_token"),
                                         ig_user_id=creds.get("ig_user_id"))
            result = provider.publish(content=post.content,
                                      media_url=post.media_urls[0] if post.media_urls else None)
        elif account.platform == "pinterest":
            from ...channels.social.providers.pinterest import PinterestProvider
            creds = account.credentials_enc or {}
            provider = PinterestProvider(access_token=creds.get("access_token"),
                                          board_id=creds.get("board_id"))
            result = provider.publish(title=post.content[:100], description=post.content,
                                      media_url=post.media_urls[0] if post.media_urls else "",
                                      link=post.link)
        else:
            return EurkaiOutput(success=False, result=None,
                                message=f"No provider for platform: {account.platform}")

        if result.get("success"):
            db_update_social_post(db, post_id, {
                "status": SocialPostStatus.published,
                "published_at": datetime.utcnow(),
                "external_id": result.get("message_id"),
                "external_url": result.get("url"),
            })
            return EurkaiOutput(success=True, result=result, message="Published")
        else:
            db_update_social_post(db, post_id, {"status": SocialPostStatus.failed, "error": result.get("error")})
            return EurkaiOutput(success=False, result=result, message="Publish failed")
    except Exception as e:
        raise HTTPException(500, str(e))

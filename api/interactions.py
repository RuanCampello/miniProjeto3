import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from database import LikedPost, User, session_deps, Post, LikedBy
from users import get_current_user

interactions_router = APIRouter()


@interactions_router.patch("/{post_id}")
async def like_post(
        session: session_deps,
        current_user: Annotated[uuid.UUID, Depends(get_current_user)],
        post_id: uuid.UUID,
):
    post_db = session.get(Post, post_id)
    if not post_db:
        raise HTTPException(status_code=404, detail="Post not found")

    like = session.exec(
        select(LikedPost).where(
            LikedPost.user_id == current_user,
            LikedPost.post_id == post_id
        )
    ).first()

    if not like:
        like_db = LikedPost(user_id=current_user, post_id=post_id)
        post_db.like_count += 1
        session.add(like_db)
    else:
        post_db.like_count -= 1
        session.delete(like)

    session.commit()
    session.add(post_db)
    session.refresh(post_db)

    return post_db.id


@interactions_router.get("/{post_id}")
async def get_how_liked(
        session: session_deps,
        current_user: Annotated[uuid.UUID, Depends(get_current_user)],
        post_id: uuid.UUID,
):
    query = (
        select(User.name, User.username, User.profile_image, LikedPost.id, LikedPost.post_id)
        .join(LikedPost, User.id == LikedPost.user_id)
        .where(LikedPost.post_id == post_id)
    )
    results = session.exec(query).all()
    return [LikedBy(**row._asdict()) for row in results]

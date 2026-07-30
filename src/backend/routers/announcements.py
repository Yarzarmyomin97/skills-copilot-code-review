"""
Announcement management endpoints for the Mergington High School API
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from bson.objectid import ObjectId
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementCreatePayload(BaseModel):
    title: Optional[str] = Field(None, max_length=120)
    message: str = Field(..., min_length=5)
    start_date: Optional[str] = Field(
        None, description="Optional start date in YYYY-MM-DD")
    expiration_date: str = Field(...,
                                 description="Expiration date in YYYY-MM-DD")


class AnnouncementUpdatePayload(BaseModel):
    title: Optional[str] = Field(None, max_length=120)
    message: Optional[str] = Field(None, min_length=5)
    start_date: Optional[str] = Field(
        None, description="Optional start date in YYYY-MM-DD")
    expiration_date: Optional[str] = Field(
        None, description="Expiration date in YYYY-MM-DD")


def parse_date_string(value: str, field_name: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
        return parsed.isoformat()
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"{field_name} must be in YYYY-MM-DD format")


def verify_teacher(username: Optional[str]) -> Dict[str, Any]:
    if not username:
        raise HTTPException(status_code=401, detail="Authentication required")

    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")

    return teacher


def serialize_announcement(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "title": doc.get("title", ""),
        "message": doc["message"],
        "start_date": doc.get("start_date"),
        "expiration_date": doc["expiration_date"],
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


@router.get("", response_model=List[Dict[str, Any]])
def list_announcements(active: bool = Query(False)) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    today = date.today().isoformat()

    if active:
        query = {
            "expiration_date": {"$gte": today},
            "$or": [
                {"start_date": {"$lte": today}},
                {"start_date": {"$exists": False}},
                {"start_date": None},
                {"start_date": ""},
            ],
        }

    docs = announcements_collection.find(query).sort("expiration_date", 1)
    return [serialize_announcement(doc) for doc in docs]


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    announcement: AnnouncementCreatePayload,
    teacher_username: str = Query(...)
) -> Dict[str, Any]:
    verify_teacher(teacher_username)

    start_date = None
    if announcement.start_date:
        start_date = parse_date_string(announcement.start_date, "start_date")

    expiration_date = parse_date_string(
        announcement.expiration_date, "expiration_date"
    )

    if start_date and start_date > expiration_date:
        raise HTTPException(
            status_code=400,
            detail="Start date cannot be after expiration date"
        )

    announcement_data = {
        "title": (announcement.title or "").strip(),
        "message": announcement.message.strip(),
        "start_date": start_date,
        "expiration_date": expiration_date,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    result = announcements_collection.insert_one(announcement_data)
    inserted_doc = announcements_collection.find_one(
        {"_id": result.inserted_id})
    return serialize_announcement(inserted_doc)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    announcement: AnnouncementUpdatePayload,
    teacher_username: str = Query(...)
) -> Dict[str, Any]:
    verify_teacher(teacher_username)

    update_fields: Dict[str, Any] = {}

    if announcement.title is not None:
        update_fields["title"] = announcement.title.strip()

    if announcement.message is not None:
        update_fields["message"] = announcement.message.strip()

    if announcement.start_date is not None:
        update_fields["start_date"] = parse_date_string(
            announcement.start_date, "start_date"
        )

    if announcement.expiration_date is not None:
        update_fields["expiration_date"] = parse_date_string(
            announcement.expiration_date, "expiration_date"
        )

    if (
        update_fields.get("start_date")
        and update_fields.get("expiration_date")
        and update_fields["start_date"] > update_fields["expiration_date"]
    ):
        raise HTTPException(
            status_code=400,
            detail="Start date cannot be after expiration date"
        )

    if not update_fields:
        raise HTTPException(
            status_code=400, detail="No announcement fields provided")

    update_fields["updated_at"] = datetime.utcnow().isoformat()

    try:
        result = announcements_collection.update_one(
            {"_id": ObjectId(announcement_id)},
            {"$set": update_fields}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement id")

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    doc = announcements_collection.find_one({"_id": ObjectId(announcement_id)})
    return serialize_announcement(doc)


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: str = Query(...)
) -> Dict[str, str]:
    verify_teacher(teacher_username)

    try:
        result = announcements_collection.delete_one(
            {"_id": ObjectId(announcement_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement id")

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement removed"}

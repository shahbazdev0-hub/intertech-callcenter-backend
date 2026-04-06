# backend/app/api/v1/analytics.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.database import get_database
from app.api.deps import get_current_admin_user
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/admin/overview")
async def get_admin_analytics_overview(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get comprehensive analytics for ALL users (Admin only).
    Uses MongoDB aggregation pipelines for performance.
    """
    try:
        logger.info(f"Admin {current_user['email']} requesting analytics overview")

        # Build date filter
        date_filter = {}
        if from_date:
            try:
                from_datetime = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
                date_filter["$gte"] = from_datetime
            except ValueError:
                pass
        if to_date:
            try:
                to_datetime = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
                date_filter["$lte"] = to_datetime
            except ValueError:
                pass

        match_filter = {}
        if date_filter:
            match_filter["created_at"] = date_filter

        # --- Run all aggregations in parallel using a single pass where possible ---

        # 1. Main stats aggregation on calls collection
        stats_pipeline = [
            {"$match": match_filter} if match_filter else {"$match": {}},
            {"$group": {
                "_id": None,
                "total_calls": {"$sum": 1},
                "completed_calls": {
                    "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}
                },
                "in_progress_calls": {
                    "$sum": {"$cond": [{"$eq": ["$status", "in-progress"]}, 1, 0]}
                },
                "failed_calls": {
                    "$sum": {"$cond": [{"$in": ["$status", ["failed", "no-answer", "busy"]]}, 1, 0]}
                },
                "total_duration": {"$sum": {"$ifNull": ["$duration", 0]}}
            }}
        ]

        # 1b. Count unique active users
        active_users_pipeline = [
            {"$match": match_filter} if match_filter else {"$match": {}},
            {"$match": {"user_id": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$user_id"}},
            {"$count": "count"}
        ]

        # 2. Outcome distribution from calls collection (exclude unknown/empty)
        outcome_pipeline = [
            {"$match": match_filter} if match_filter else {"$match": {}},
            {"$match": {"outcome": {"$exists": True, "$ne": None, "$ne": "", "$nin": ["unknown", "Unknown"]}}},
            {"$group": {"_id": {"$toLower": "$outcome"}, "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]

        # 3. Sentiment distribution from calls collection (exclude unknown/empty)
        sentiment_pipeline = [
            {"$match": match_filter} if match_filter else {"$match": {}},
            {"$match": {"sentiment": {"$exists": True, "$ne": None, "$ne": "", "$nin": ["unknown", "Unknown"]}}},
            {"$group": {"_id": {"$toLower": "$sentiment"}, "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]

        # 4. Call trends by date
        trends_pipeline = [
            {"$match": match_filter} if match_filter else {"$match": {}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "calls": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]

        # 5. Hourly distribution
        hourly_pipeline = [
            {"$match": match_filter} if match_filter else {"$match": {}},
            {"$group": {
                "_id": {"$hour": "$created_at"},
                "calls": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]

        # 6. Top users by call count
        top_users_pipeline = [
            {"$match": match_filter} if match_filter else {"$match": {}},
            {"$match": {"user_id": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$user_id", "call_count": {"$sum": 1}}},
            {"$sort": {"call_count": -1}},
            {"$limit": 10}
        ]

        # 7. Total users count
        total_users = await db.users.count_documents({})

        # Execute all pipelines
        stats_result = await db.calls.aggregate(stats_pipeline).to_list(length=1)
        active_users_result = await db.calls.aggregate(active_users_pipeline).to_list(length=1)
        outcome_result = await db.calls.aggregate(outcome_pipeline).to_list(length=20)
        sentiment_result = await db.calls.aggregate(sentiment_pipeline).to_list(length=10)
        trends_result = await db.calls.aggregate(trends_pipeline).to_list(length=365)
        hourly_result = await db.calls.aggregate(hourly_pipeline).to_list(length=24)
        top_users_result = await db.calls.aggregate(top_users_pipeline).to_list(length=10)

        # Process stats
        stats = stats_result[0] if stats_result else {
            "total_calls": 0, "completed_calls": 0, "in_progress_calls": 0,
            "failed_calls": 0, "total_duration": 0
        }

        total_calls = stats.get("total_calls", 0)
        active_users = active_users_result[0]["count"] if active_users_result else 0
        total_duration = stats.get("total_duration", 0)
        avg_duration = total_duration / total_calls if total_calls > 0 else 0

        # Process outcomes
        outcomes_dict = {}
        outcome_data = []
        for item in outcome_result:
            key = str(item["_id"]) if item["_id"] else "unknown"
            name = key.replace('_', ' ').title()
            outcomes_dict[key] = item["count"]
            outcome_data.append({"name": name, "value": item["count"]})

        successful_calls = outcomes_dict.get("successful", 0) + outcomes_dict.get("converted", 0)
        total_with_outcome = sum(item["count"] for item in outcome_result)
        success_rate = (successful_calls / total_with_outcome * 100) if total_with_outcome > 0 else 0

        # Process sentiments
        sentiments_dict = {}
        sentiment_data = []
        for item in sentiment_result:
            key = str(item["_id"]) if item["_id"] else "neutral"
            name = key.capitalize()
            sentiments_dict[key] = item["count"]
            sentiment_data.append({"name": name, "value": item["count"]})

        # Process trends
        trends_data = [
            {"date": item["_id"], "calls": item["calls"]}
            for item in trends_result
        ]

        # Process hourly
        hourly_data = [
            {"hour": f"{item['_id']:02d}:00", "calls": item["calls"]}
            for item in hourly_result
        ]

        # Process top users — batch fetch user details
        top_user_ids = [str(item["_id"]) for item in top_users_result if item["_id"]]
        user_obj_ids = []
        for uid in top_user_ids:
            if ObjectId.is_valid(uid):
                user_obj_ids.append(ObjectId(uid))

        user_details = {}
        if user_obj_ids:
            users_cursor = db.users.find(
                {"_id": {"$in": user_obj_ids}},
                {"full_name": 1, "email": 1, "company": 1}
            )
            async for u in users_cursor:
                user_details[str(u["_id"])] = {
                    "name": u.get("full_name", "Unknown"),
                    "email": u.get("email", ""),
                    "company": u.get("company", "")
                }

        top_users = [
            {
                "user_id": str(item["_id"]),
                "name": user_details.get(str(item["_id"]), {}).get("name", "Unknown"),
                "email": user_details.get(str(item["_id"]), {}).get("email", ""),
                "company": user_details.get(str(item["_id"]), {}).get("company", ""),
                "call_count": item["call_count"]
            }
            for item in top_users_result
        ]

        conversion_rate = (outcomes_dict.get("converted", 0) / total_with_outcome * 100) if total_with_outcome > 0 else 0

        return {
            "overview": {
                "total_calls": total_calls,
                "completed_calls": stats.get("completed_calls", 0),
                "in_progress_calls": stats.get("in_progress_calls", 0),
                "failed_calls": stats.get("failed_calls", 0),
                "total_duration_seconds": total_duration,
                "avg_duration_seconds": round(avg_duration, 2),
                "success_rate": round(success_rate, 2),
                "total_users": total_users,
                "active_users": active_users,
                "conversion_rate": round(conversion_rate, 2)
            },
            "call_trends": trends_data,
            "outcome_distribution": outcome_data,
            "sentiment_distribution": sentiment_data,
            "top_users": top_users,
            "hourly_distribution": hourly_data,
            "outcomes_summary": outcomes_dict,
            "sentiments_summary": sentiments_dict
        }

    except Exception as e:
        logger.error(f"Error fetching admin analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch analytics: {str(e)}"
        )


@router.get("/admin/user-analytics/{user_id}")
async def get_user_analytics(
    user_id: str,
    current_user: dict = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get detailed analytics for a specific user (Admin only)"""
    try:
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID")

        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Aggregation for user stats
        stats_pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": None,
                "total_calls": {"$sum": 1},
                "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
                "total_duration": {"$sum": {"$ifNull": ["$duration", 0]}}
            }}
        ]

        outcome_pipeline = [
            {"$match": {"user_id": user_id, "outcome": {"$exists": True, "$ne": None, "$ne": ""}}},
            {"$group": {"_id": "$outcome", "count": {"$sum": 1}}}
        ]

        stats_result = await db.calls.aggregate(stats_pipeline).to_list(length=1)
        outcome_result = await db.calls.aggregate(outcome_pipeline).to_list(length=20)

        stats = stats_result[0] if stats_result else {"total_calls": 0, "completed": 0, "total_duration": 0}
        outcomes = {str(item["_id"]): item["count"] for item in outcome_result}

        total_calls = stats.get("total_calls", 0)
        total_duration = stats.get("total_duration", 0)

        # Recent calls
        recent_calls = await db.calls.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(10).to_list(length=10)

        return {
            "user": {
                "id": str(user["_id"]),
                "name": user.get("full_name"),
                "email": user.get("email"),
                "company": user.get("company")
            },
            "statistics": {
                "total_calls": total_calls,
                "completed_calls": stats.get("completed", 0),
                "total_duration": total_duration,
                "avg_duration": total_duration / total_calls if total_calls > 0 else 0,
                "outcomes": outcomes
            },
            "recent_calls": [
                {
                    "_id": str(call["_id"]),
                    "to_number": call.get("to_number"),
                    "status": call.get("status"),
                    "duration": call.get("duration"),
                    "created_at": call.get("created_at")
                }
                for call in recent_calls
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user analytics: {str(e)}"
        )


@router.get("/admin/call-details")
async def get_all_calls_with_logs(
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = Query(None),
    outcome_filter: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get all calls with user details using aggregation (Admin only)"""
    try:
        filter_query = {}

        if status_filter:
            filter_query["status"] = status_filter
        if outcome_filter:
            filter_query["outcome"] = outcome_filter

        date_filter = {}
        if from_date:
            date_filter["$gte"] = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
        if to_date:
            date_filter["$lte"] = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        if date_filter:
            filter_query["created_at"] = date_filter

        total_count = await db.calls.count_documents(filter_query)

        # Fetch calls with pagination
        calls = await db.calls.find(filter_query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)

        # Batch-fetch user details
        user_ids = set()
        for call in calls:
            uid = call.get("user_id")
            if uid and ObjectId.is_valid(uid):
                user_ids.add(uid)

        user_map = {}
        if user_ids:
            user_oids = [ObjectId(uid) for uid in user_ids]
            users_cursor = db.users.find(
                {"_id": {"$in": user_oids}},
                {"full_name": 1, "email": 1, "company": 1}
            )
            async for u in users_cursor:
                user_map[str(u["_id"])] = u

        enriched_calls = []
        for call in calls:
            uid = call.get("user_id")
            user = user_map.get(uid) if uid else None

            enriched_call = {
                "_id": str(call["_id"]),
                "call_sid": call.get("call_sid") or call.get("twilio_call_sid"),
                "from_number": call.get("from_number"),
                "to_number": call.get("to_number"),
                "status": call.get("status"),
                "duration": call.get("duration", 0),
                "created_at": call.get("created_at"),
                "ended_at": call.get("ended_at"),
                "user": {
                    "id": str(user["_id"]) if user else None,
                    "name": user.get("full_name") if user else "Unknown",
                    "email": user.get("email") if user else "",
                    "company": user.get("company") if user else ""
                } if user else None,
                "log": {
                    "summary": call.get("ai_summary") or call.get("summary", ""),
                    "outcome": call.get("outcome", ""),
                    "sentiment": call.get("sentiment", ""),
                    "keywords": call.get("keywords", []),
                } if call.get("outcome") or call.get("sentiment") or call.get("ai_summary") else None
            }
            enriched_calls.append(enriched_call)

        return {
            "calls": enriched_calls,
            "total": total_count,
            "page": skip // limit + 1,
            "pages": (total_count + limit - 1) // limit
        }

    except Exception as e:
        logger.error(f"Error fetching call details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch call details: {str(e)}"
        )

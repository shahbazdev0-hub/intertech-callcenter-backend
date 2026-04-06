

# backend/app/api/v1/calls.py -orginal file

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from typing import Optional
from datetime import datetime, timedelta
from bson import ObjectId
from pathlib import Path

from app.api.deps import get_current_user
from app.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================
# ✅ LIST ALL CALLS
# ============================================

@router.get("/")
async def list_calls(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    ✅ List all calls for the current user with filters
    """
    try:
        user_id_str = str(current_user["_id"])

        # Build query
        query = {"user_id": user_id_str}

        if status:
            query["status"] = status

        if direction:
            query["direction"] = direction
        
        # Date range filter
        if from_date or to_date:
            query["created_at"] = {}
            if from_date:
                query["created_at"]["$gte"] = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            if to_date:
                query["created_at"]["$lte"] = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        
        logger.info(f"📞 Listing calls with query: {query}")
        
        # Get total count
        total = await db.calls.count_documents(query)
        
        # Get calls
        cursor = db.calls.find(query).sort("created_at", -1).skip(skip).limit(limit)
        calls = await cursor.to_list(length=limit)
        
        # Format calls - Convert ObjectIds to strings
        formatted_calls = []
        for call in calls:
            formatted_call = {
                "id": str(call["_id"]),
                "twilio_call_sid": call.get("twilio_call_sid"),
                "from_number": call.get("from_number"),
                "to_number": call.get("to_number"),
                "status": call.get("status"),
                "direction": call.get("direction"),
                "duration": call.get("duration", 0),
                "recording_url": call.get("recording_url"),
                "recording_sid": call.get("recording_sid"),
                "recording_duration": call.get("recording_duration", 0),
                "agent_id": str(call["agent_id"]) if call.get("agent_id") else None,
                "user_id": str(call["user_id"]) if call.get("user_id") else None,
                "created_at": call.get("created_at").isoformat() if call.get("created_at") else None,
                "started_at": call.get("started_at").isoformat() if call.get("started_at") else None,
                "ended_at": call.get("ended_at").isoformat() if call.get("ended_at") else None,
            }
            formatted_calls.append(formatted_call)
        
        logger.info(f"✅ Found {len(formatted_calls)} calls")
        
        return {
            "calls": formatted_calls,
            "total": total,
            "page": skip // limit + 1 if limit > 0 else 1,
            "page_size": limit
        }
        
    except Exception as e:
        logger.error(f"❌ Error listing calls: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list calls: {str(e)}"
        )


# ============================================
# ✅ GET ALL CALL LOGS (OPTIMIZED - NO TIMEOUT)
# ============================================

@router.get("/logs/all")
async def get_all_call_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    outcome: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    ✅ OPTIMIZED: Get all call logs WITHOUT loading all transcripts (prevents timeout)
    """
    try:
        user_id_str = str(current_user["_id"])
        
        # Build query for calls
        call_query = {"user_id": user_id_str}
        
        # Date range filter
        if from_date or to_date:
            call_query["created_at"] = {}
            if from_date:
                call_query["created_at"]["$gte"] = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            if to_date:
                call_query["created_at"]["$lte"] = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        
        # Apply outcome/sentiment filters at DB level
        if outcome:
            call_query["outcome"] = outcome
        if sentiment:
            call_query["sentiment"] = sentiment

        # Text search filter (phone numbers, summary, keywords)
        if search:
            search_regex = {"$regex": search, "$options": "i"}
            call_query["$or"] = [
                {"from_number": search_regex},
                {"to_number": search_regex},
                {"summary": search_regex},
                {"keywords": search_regex},
            ]

        logger.info(f"📞 Getting call logs with query: {call_query}")

        # Use aggregation with $lookup to get transcript counts in a single query
        pipeline = [
            {"$match": call_query},
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit},
            {"$lookup": {
                "from": "call_transcripts",
                "let": {"call_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$call_id", "$$call_id"]}}},
                    {"$count": "count"}
                ],
                "as": "transcript_info"
            }},
            {"$addFields": {
                "transcript_count": {
                    "$ifNull": [{"$arrayElemAt": ["$transcript_info.count", 0]}, 0]
                }
            }},
            {"$project": {"transcript_info": 0}}
        ]

        calls = await db.calls.aggregate(pipeline).to_list(length=limit)

        call_logs = []
        for call in calls:
            call_id = call["_id"]
            log = {
                "id": str(call_id),
                "_id": str(call_id),
                "call_sid": call.get("twilio_call_sid"),
                "from_number": call.get("from_number", ""),
                "to_number": call.get("to_number", ""),
                "status": call.get("status", ""),
                "direction": call.get("direction", "outbound"),
                "duration": call.get("duration", 0),
                "recording_url": call.get("recording_url", ""),
                "recording_duration": call.get("recording_duration", 0),
                "transcript_count": call.get("transcript_count", 0),
                "summary": call.get("ai_summary") or f"Call with {call.get('to_number', 'unknown')} - {call.get('duration', 0)}s",
                "outcome": call.get("outcome") or ("completed" if call.get("status") == "completed" else "pending"),
                "sentiment": call.get("sentiment", "neutral"),
                "keywords": call.get("keywords", []),
                "key_messages": call.get("key_messages", []),
                "created_at": call.get("created_at").isoformat() if call.get("created_at") else None,
                "ended_at": call.get("ended_at").isoformat() if call.get("ended_at") else None,
            }
            call_logs.append(log)

        total = await db.calls.count_documents(call_query)
        
        logger.info(f"✅ Retrieved {len(call_logs)} call logs (optimized)")
        
        # ✅ FIX: Return in format expected by frontend
        return {
            "logs": call_logs,  # Frontend expects response.data.logs
            "total": total,
            "page": skip // limit + 1 if limit > 0 else 1,
            "page_size": limit
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting call logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get call logs: {str(e)}"
        )


# ============================================
# GET SINGLE CALL LOG
# ============================================

@router.get("/{call_id}/log")
async def get_call_log(
    call_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get detailed log for a specific call"""
    try:
        if not ObjectId.is_valid(call_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid call ID"
            )
        
        user_id_str = str(current_user["_id"])
        
        # Get call
        call = await db.calls.find_one({
            "_id": ObjectId(call_id),
            "user_id": user_id_str
        })
        
        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found"
            )
        
        # Get transcripts
        transcripts_cursor = db.call_transcripts.find({"call_id": ObjectId(call_id)}).sort("timestamp", 1)
        transcripts = await transcripts_cursor.to_list(length=None)
        
        formatted_transcripts = []
        for t in transcripts:
            formatted_transcripts.append({
                "speaker": t.get("speaker"),
                "text": t.get("text", ""),
                "timestamp": t.get("timestamp").isoformat() if t.get("timestamp") else None,
                "confidence": t.get("confidence")
            })
        
        return {
            "call_id": str(call["_id"]),
            "call_sid": call.get("twilio_call_sid"),
            "from_number": call.get("from_number"),
            "to_number": call.get("to_number"),
            "status": call.get("status"),
            "duration": call.get("duration", 0),
            "transcripts": formatted_transcripts,
            "recording_url": call.get("recording_url"),
            "created_at": call.get("created_at").isoformat() if call.get("created_at") else None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting call log: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting call log: {str(e)}"
        )


# ============================================
# DASHBOARD OVERVIEW - Single optimized endpoint
# ============================================

@router.get("/dashboard/overview")
async def get_dashboard_overview(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Single optimized endpoint for dashboard overview.
    Uses MongoDB aggregation instead of loading all documents into memory.
    Returns: call stats, recent calls, agent count, SMS/email/appointment counts, 7-day trend.
    """
    try:
        user_id_str = str(current_user["_id"])
        now = datetime.utcnow()
        start_of_today = datetime(now.year, now.month, now.day)
        seven_days_ago = now - timedelta(days=7)

        # Run all queries in parallel using asyncio.gather
        import asyncio

        # 1. Call stats aggregation (single query for all stats)
        async def get_call_stats():
            pipeline = [
                {"$match": {"user_id": user_id_str}},
                {"$facet": {
                    "totals": [{"$group": {
                        "_id": None,
                        "total_calls": {"$sum": 1},
                        "total_duration": {"$sum": {"$ifNull": ["$duration", 0]}},
                        "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
                        "outbound": {"$sum": {"$cond": [{"$eq": ["$direction", "outbound"]}, 1, 0]}},
                    }}],
                    "today": [
                        {"$match": {"created_at": {"$gte": start_of_today}}},
                        {"$count": "count"}
                    ],
                    "recent": [
                        {"$sort": {"created_at": -1}},
                        {"$limit": 8},
                        {"$project": {
                            "_id": 1, "to_number": 1, "from_number": 1, "phone_number": 1,
                            "created_at": 1, "duration": 1, "status": 1, "direction": 1, "outcome": 1
                        }}
                    ],
                    "trend": [
                        {"$match": {"created_at": {"$gte": seven_days_ago}}},
                        {"$group": {
                            "_id": {"$dateToString": {"format": "%b %d", "date": "$created_at"}},
                            "calls": {"$sum": 1}
                        }},
                        {"$sort": {"_id": 1}}
                    ]
                }}
            ]
            result = await db.calls.aggregate(pipeline).to_list(length=1)
            return result[0] if result else {}

        # 2. Agent count
        async def get_agent_count():
            return await db.voice_agents.count_documents({"user_id": user_id_str, "is_active": True})

        # 3. SMS count
        async def get_sms_count():
            return await db.sms_logs.count_documents({"user_id": user_id_str, "direction": "outbound"})

        # 4. Email count
        async def get_email_count():
            return await db.email_logs.count_documents({"user_id": user_id_str, "direction": "outbound"})

        # 5. Appointment count
        async def get_appointment_count():
            return await db.appointments.count_documents({"user_id": user_id_str})

        # Execute all in parallel
        call_data, active_agents, sms_sent, emails_sent, total_appointments = await asyncio.gather(
            get_call_stats(),
            get_agent_count(),
            get_sms_count(),
            get_email_count(),
            get_appointment_count()
        )

        # Extract call stats
        totals = call_data.get("totals", [{}])
        totals = totals[0] if totals else {}
        today_list = call_data.get("today", [])
        calls_today = today_list[0]["count"] if today_list else 0
        recent_calls = call_data.get("recent", [])
        trend_raw = call_data.get("trend", [])

        total_calls = totals.get("total_calls", 0)
        total_duration = totals.get("total_duration", 0)
        completed = totals.get("completed", 0)
        outbound = totals.get("outbound", 0)

        success_rate = round((completed / total_calls * 100), 1) if total_calls > 0 else 0
        total_minutes = round(total_duration / 60)
        avg_duration_sec = total_duration // total_calls if total_calls > 0 else 0
        avg_min = avg_duration_sec // 60
        avg_sec = avg_duration_sec % 60

        # Build 7-day trend with all dates filled
        trend_map = {t["_id"]: t["calls"] for t in trend_raw}
        trend_data = []
        for i in range(7):
            d = seven_days_ago + timedelta(days=i)
            date_str = d.strftime("%b %d")
            trend_data.append({"date": date_str, "calls": trend_map.get(date_str, 0)})

        # Format recent calls
        formatted_recent = []
        for call in recent_calls:
            call_id = str(call.get("_id", ""))
            created = call.get("created_at")
            duration = call.get("duration", 0)
            mins = duration // 60 if duration else 0
            secs = duration % 60 if duration else 0

            formatted_recent.append({
                "id": call_id,
                "customer": call.get("to_number") or call.get("from_number") or call.get("phone_number") or "Unknown",
                "time": created.strftime("%I:%M %p").lstrip("0") if created else "N/A",
                "duration": f"{mins}:{str(secs).zfill(2)}",
                "status": call.get("status", "unknown"),
                "direction": call.get("direction", "outbound"),
                "type": call.get("outcome") or ("support" if call.get("direction") == "inbound" else "sales")
            })

        return {
            "success": True,
            "stats": {
                "callsToday": calls_today,
                "successRate": success_rate,
                "revenue": round(calls_today * 2.5, 2),
                "totalCalls": total_calls,
                "totalMinutes": total_minutes,
                "callsInitiated": outbound,
                "activeAgents": active_agents,
                "avgCallDuration": f"{avg_min}m {avg_sec}s",
                "conversionRate": round(success_rate * 0.25, 1),
                "messagesSent": sms_sent,
                "emailsSent": emails_sent,
                "totalAppointments": total_appointments
            },
            "recentCalls": formatted_recent,
            "callTrends": trend_data
        }

    except Exception as e:
        logger.error(f"Error in dashboard overview: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading dashboard: {str(e)}"
        )


# ============================================
# GET CALL STATISTICS
# ============================================

@router.get("/stats/summary")
async def get_call_stats(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get call statistics summary"""
    try:
        user_id_str = str(current_user["_id"])
        
        # Build date filter
        filter_query = {"user_id": user_id_str}
        
        if from_date or to_date:
            date_filter = {}
            if from_date:
                date_filter["$gte"] = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            if to_date:
                date_filter["$lte"] = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
            filter_query["created_at"] = date_filter
        
        # Use aggregation instead of loading all calls into memory
        pipeline = [
            {"$match": filter_query},
            {"$group": {
                "_id": None,
                "total_calls": {"$sum": 1},
                "total_duration": {"$sum": {"$ifNull": ["$duration", 0]}},
                "completed_calls": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
                "in_progress_calls": {"$sum": {"$cond": [{"$eq": ["$status", "in-progress"]}, 1, 0]}},
                "failed_calls": {"$sum": {"$cond": [{"$in": ["$status", ["failed", "no-answer", "busy"]]}, 1, 0]}},
                "inbound_calls": {"$sum": {"$cond": [{"$eq": ["$direction", "inbound"]}, 1, 0]}},
                "outbound_calls": {"$sum": {"$cond": [{"$eq": ["$direction", "outbound"]}, 1, 0]}},
            }}
        ]
        result = await db.calls.aggregate(pipeline).to_list(length=1)
        s = result[0] if result else {}

        total_calls = s.get("total_calls", 0)
        total_duration = s.get("total_duration", 0)
        avg_duration = total_duration / total_calls if total_calls > 0 else 0

        return {
            "success": True,
            "stats": {
                "total_calls": total_calls,
                "completed_calls": s.get("completed_calls", 0),
                "in_progress_calls": s.get("in_progress_calls", 0),
                "failed_calls": s.get("failed_calls", 0),
                "total_duration": total_duration,
                "avg_duration": round(avg_duration, 2),
                "inbound_calls": s.get("inbound_calls", 0),
                "outbound_calls": s.get("outbound_calls", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting call stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting call stats: {str(e)}"
        )


# ============================================
# GET CALL ANALYTICS DATA (NEW - FOR CALLANALYTICS PAGE)
# ============================================

@router.get("/analytics/data")
async def get_call_analytics_data(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get comprehensive analytics data for CallAnalytics page
    Includes: stats, call trends, outcome distribution
    """
    try:
        user_id_str = str(current_user["_id"])
        
        # Build date filter
        filter_query = {"user_id": user_id_str}
        
        # Calculate date range based on days parameter if not provided
        if not from_date:
            from_datetime = datetime.now() - timedelta(days=days)
        else:
            from_datetime = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            
        if not to_date:
            to_datetime = datetime.now()
        else:
            to_datetime = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        
        filter_query["created_at"] = {
            "$gte": from_datetime,
            "$lte": to_datetime
        }
        
        logger.info(f"📊 Fetching analytics data for date range: {from_datetime} to {to_datetime}")

        # Single aggregation pipeline for all stats, trends, and outcomes
        pipeline = [
            {"$match": filter_query},
            {"$facet": {
                "stats": [{"$group": {
                    "_id": None,
                    "total_calls": {"$sum": 1},
                    "total_duration": {"$sum": {"$ifNull": ["$duration", 0]}},
                    "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
                    "in_progress": {"$sum": {"$cond": [{"$eq": ["$status", "in-progress"]}, 1, 0]}},
                    "failed": {"$sum": {"$cond": [{"$in": ["$status", ["failed", "no-answer", "busy"]]}, 1, 0]}},
                }}],
                "trends": [
                    {"$group": {
                        "_id": {"$dateToString": {"format": "%b %d", "date": "$created_at"}},
                        "calls": {"$sum": 1}
                    }},
                    {"$sort": {"_id": 1}}
                ],
                "outcomes": [
                    {"$group": {
                        "_id": "$status",
                        "count": {"$sum": 1}
                    }}
                ]
            }}
        ]

        result = await db.calls.aggregate(pipeline).to_list(length=1)
        data = result[0] if result else {}

        # Extract stats
        stats_raw = data.get("stats", [{}])
        s = stats_raw[0] if stats_raw else {}
        total_calls = s.get("total_calls", 0)
        total_duration = s.get("total_duration", 0)
        avg_duration = total_duration / total_calls if total_calls > 0 else 0

        # Build trend data with all dates filled
        trend_map = {t["_id"]: t["calls"] for t in data.get("trends", [])}
        trend_data = []
        current_date = from_datetime
        while current_date <= to_datetime:
            date_str = current_date.strftime("%b %d")
            trend_data.append({"date": date_str, "calls": trend_map.get(date_str, 0)})
            current_date += timedelta(days=1)

        # Map outcomes
        outcome_map = {"completed": "Successful", "failed": "Unsuccessful", "busy": "Unsuccessful",
                       "no-answer": "No Answer", "in-progress": "Needs Followup"}
        outcomes = {}
        for o in data.get("outcomes", []):
            label = outcome_map.get(o["_id"], "Other")
            outcomes[label] = outcomes.get(label, 0) + o["count"]
        outcome_data = [{"name": n, "value": v} for n, v in outcomes.items() if v > 0]

        response_data = {
            "success": True,
            "stats": {
                "total_calls": total_calls,
                "completed_calls": s.get("completed", 0),
                "average_duration": round(avg_duration, 2),
                "in_progress_calls": s.get("in_progress", 0),
                "failed_calls": s.get("failed", 0)
            },
            "call_trends": trend_data,
            "outcome_data": outcome_data,
            "date_range": {
                "from": from_datetime.isoformat(),
                "to": to_datetime.isoformat(),
                "days": days
            }
        }

        logger.info(f"✅ Analytics data generated: {total_calls} calls, {len(trend_data)} trend points")

        return response_data
        
    except Exception as e:
        logger.error(f"❌ Error getting analytics data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting analytics data: {str(e)}"
        )


# ============================================
# RECORDING ENDPOINTS
# ============================================

@router.get("/{call_id}/recording")
async def get_call_recording(
    call_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get call recording URL"""
    try:
        if not ObjectId.is_valid(call_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid call ID"
            )
        
        user_id_str = str(current_user["_id"])
        
        call = await db.calls.find_one({
            "_id": ObjectId(call_id),
            "user_id": user_id_str
        })
        
        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found"
            )
        
        recording_url = call.get("recording_url")
        
        if not recording_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not available for this call"
            )
        
        return {
            "success": True,
            "recording_url": recording_url,
            "recording_sid": call.get("recording_sid"),
            "recording_duration": call.get("recording_duration", 0),
            "downloaded": call.get("recording_downloaded", False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching recording: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching recording: {str(e)}"
        )


# ============================================
# ✅ DOWNLOAD RECORDING FROM TWILIO TO LOCAL
# ============================================

@router.post("/{call_id}/recording/download")
async def download_recording_from_twilio(
    call_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Download recording from Twilio and save locally"""
    import httpx
    import os
    from pathlib import Path
    
    try:
        if not ObjectId.is_valid(call_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid call ID"
            )
        
        user_id_str = str(current_user["_id"])
        
        call = await db.calls.find_one({
            "_id": ObjectId(call_id),
            "user_id": user_id_str
        })
        
        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found"
            )
        
        recording_url = call.get("recording_url")
        recording_sid = call.get("recording_sid")
        
        if not recording_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No recording URL available for this call"
            )
        
        # Check if already downloaded
        if call.get("recording_downloaded") and call.get("local_recording_path"):
            local_path = call.get("local_recording_path")
            if os.path.exists(local_path):
                logger.info(f"✅ Recording already downloaded: {local_path}")
                return {
                    "success": True,
                    "message": "Recording already downloaded",
                    "local_path": local_path,
                    "already_downloaded": True
                }
        
        # Create recordings directory
        recordings_dir = Path("recordings")
        recordings_dir.mkdir(exist_ok=True)
        
        # Generate filename
        filename = f"{recording_sid or call_id}.mp3"
        local_path = recordings_dir / filename
        
        # Download from Twilio (ensure .mp3 extension — not double-appended)
        download_url = recording_url if recording_url.endswith(".mp3") else f"{recording_url}.mp3"
        
        # Twilio requires authentication
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        logger.info(f"📥 Downloading recording from: {download_url}")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                download_url,
                auth=(account_sid, auth_token),
                follow_redirects=True,
                timeout=60.0
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Failed to download: {response.status_code}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to download recording: {response.status_code}"
                )
            
            # Save to file
            with open(local_path, "wb") as f:
                f.write(response.content)
        
        # Update database
        await db.calls.update_one(
            {"_id": ObjectId(call_id)},
            {
                "$set": {
                    "local_recording_path": str(local_path),
                    "local_recording_filename": filename,
                    "recording_downloaded": True,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"✅ Recording downloaded: {local_path}")
        
        return {
            "success": True,
            "message": "Recording downloaded successfully",
            "local_path": str(local_path),
            "filename": filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error downloading recording: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading recording: {str(e)}"
        )


# ============================================
# ✅ PLAY/STREAM RECORDING - FIXED
# ============================================

@router.get("/{call_id}/recording/play")
async def play_recording(
    call_id: str,
    token: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Stream recording audio file"""
    from fastapi.responses import FileResponse
    import os
    
    try:
        if not ObjectId.is_valid(call_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid call ID"
            )
        
        # Validate token
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token required"
            )
        
        # ✅ FIXED: Use decode_token (not decode_access_token)
        from app.core.security import decode_token
        try:
            payload = decode_token(token)
            if not payload:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
            
            # ✅ FIXED: Token contains user_id in "sub", not email
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload"
                )
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # ✅ FIXED: Get user by ID (not email)
        if not ObjectId.is_valid(user_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID in token"
            )
        
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        user_id_str = str(user["_id"])
        
        # Get call
        call = await db.calls.find_one({
            "_id": ObjectId(call_id),
            "user_id": user_id_str
        })
        
        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found"
            )
        
        local_path = call.get("local_recording_path")
        
        if not local_path or not os.path.exists(local_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording file not found. Please download first."
            )
        
        logger.info(f"🎵 Streaming recording: {local_path}")
        
        return FileResponse(
            path=local_path,
            media_type="audio/mpeg",
            filename=call.get("local_recording_filename", "recording.mp3")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error playing recording: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error playing recording: {str(e)}"
        )


# ============================================
# ✅ GET ALL RECORDINGS (SIMPLIFIED)
# ============================================

@router.get("/recordings/all")
async def get_all_recordings(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get all calls that have recordings"""
    try:
        user_id_str = str(current_user["_id"])
        
        # Query for completed calls with recording_url
        query = {
            "user_id": user_id_str,
            "recording_url": {"$exists": True, "$nin": [None, "", "null"]}
        }
        
        total = await db.calls.count_documents(query)
        
        cursor = db.calls.find(query).sort("created_at", -1).skip(skip).limit(limit)
        calls = await cursor.to_list(length=limit)
        
        recordings = []
        for call in calls:
            recordings.append({
                "id": str(call["_id"]),
                "call_id": str(call["_id"]),
                "call_sid": call.get("twilio_call_sid"),
                "from_number": call.get("from_number"),
                "to_number": call.get("to_number"),
                "direction": call.get("direction", "outbound"),
                "duration": call.get("duration", 0),
                "recording_url": call.get("recording_url"),
                "recording_sid": call.get("recording_sid"),
                "recording_duration": call.get("recording_duration", 0),
                "recording_downloaded": call.get("recording_downloaded", False),
                "local_recording_path": call.get("local_recording_path"),
                "status": call.get("status"),
                "created_at": call.get("created_at").isoformat() if call.get("created_at") else None
            })
        
        logger.info(f"✅ Found {len(recordings)} recordings")
        
        return {
            "success": True,
            "recordings": recordings,
            "total": total,
            "page": skip // limit + 1 if limit > 0 else 1,
            "page_size": limit
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting recordings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting recordings: {str(e)}"
        )


# ============================================
# ✅ GET SINGLE CALL BY ID (must be LAST to avoid catching /logs/all etc.)
# ============================================

@router.get("/{call_id}")
async def get_call(
    call_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a single call by ID (MongoDB _id or call_sid)"""
    try:
        user_id_str = str(current_user["_id"])

        call = None
        try:
            call = await db.calls.find_one({"_id": ObjectId(call_id), "user_id": user_id_str})
        except Exception:
            pass

        if not call:
            call = await db.calls.find_one({"call_sid": call_id, "user_id": user_id_str})

        if not call:
            raise HTTPException(status_code=404, detail="Call not found")

        call["_id"] = str(call["_id"])
        if call.get("created_at"):
            call["created_at"] = call["created_at"].isoformat()
        if call.get("updated_at"):
            call["updated_at"] = call["updated_at"].isoformat()

        return {"success": True, "call": call}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call: {e}")
        raise HTTPException(status_code=500, detail=str(e))
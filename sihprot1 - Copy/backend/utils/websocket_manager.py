from fastapi import WebSocket
from typing import Dict, List, Set
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        # Store connections by user type and user ID
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {
            'admin': {},
            'teacher': {},
            'student': {}
        }
        
        # Store user sessions
        self.user_sessions: Dict[str, Dict[str, str]] = {}
    
    async def connect(self, websocket: WebSocket, user_type: str, user_id: str):
        """Accept a WebSocket connection and store it"""
        await websocket.accept()
        
        # Initialize user type dict if not exists
        if user_type not in self.active_connections:
            self.active_connections[user_type] = {}
        
        # Store the connection
        self.active_connections[user_type][user_id] = websocket
        
        # Store session info
        self.user_sessions[f"{user_type}_{user_id}"] = {
            'user_type': user_type,
            'user_id': user_id,
            'connected_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"WebSocket connection established: {user_type}:{user_id}")
        
        # Send connection confirmation
        await self.send_personal_message({
            "type": "connection_established",
            "message": "Successfully connected to real-time updates",
            "user_type": user_type,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }, user_type, user_id)
    
    def disconnect(self, websocket: WebSocket, user_type: str, user_id: str):
        """Remove a WebSocket connection"""
        try:
            if (user_type in self.active_connections and 
                user_id in self.active_connections[user_type]):
                del self.active_connections[user_type][user_id]
            
            session_key = f"{user_type}_{user_id}"
            if session_key in self.user_sessions:
                del self.user_sessions[session_key]
            
            logger.info(f"WebSocket connection closed: {user_type}:{user_id}")
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {e}")
    
    async def send_personal_message(self, message: dict, user_type: str, user_id: str):
        """Send a message to a specific user"""
        try:
            if (user_type in self.active_connections and 
                user_id in self.active_connections[user_type]):
                websocket = self.active_connections[user_type][user_id]
                await websocket.send_text(json.dumps(message))
                logger.debug(f"Message sent to {user_type}:{user_id}")
            else:
                logger.warning(f"User not connected: {user_type}:{user_id}")
        except Exception as e:
            logger.error(f"Error sending message to {user_type}:{user_id}: {e}")
            # Remove broken connection
            self.disconnect(None, user_type, user_id)
    
    async def broadcast_to_user_type(self, message: dict, user_type: str):
        """Broadcast a message to all users of a specific type"""
        if user_type not in self.active_connections:
            return
        
        disconnected_users = []
        
        for user_id, websocket in self.active_connections[user_type].items():
            try:
                await websocket.send_text(json.dumps(message))
                logger.debug(f"Broadcast sent to {user_type}:{user_id}")
            except Exception as e:
                logger.error(f"Error broadcasting to {user_type}:{user_id}: {e}")
                disconnected_users.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected_users:
            self.disconnect(None, user_type, user_id)
    
    async def broadcast_to_all(self, message: dict):
        """Broadcast a message to all connected users"""
        for user_type in self.active_connections:
            await self.broadcast_to_user_type(message, user_type)
    
    async def broadcast_to_admins(self, message: dict):
        """Broadcast a message to all admin users"""
        await self.broadcast_to_user_type(message, 'admin')
    
    async def broadcast_to_teachers(self, message: dict):
        """Broadcast a message to all teacher users"""
        await self.broadcast_to_user_type(message, 'teacher')
    
    async def broadcast_to_students(self, message: dict):
        """Broadcast a message to all student users"""
        await self.broadcast_to_user_type(message, 'student')
    
    async def notify_timetable_update(self, batch_ids: List[str] = None):
        """Notify users about timetable updates"""
        message = {
            "type": "timetable_updated",
            "message": "Timetable has been updated",
            "timestamp": datetime.utcnow().isoformat(),
            "affected_batches": batch_ids
        }
        
        # Notify all users
        await self.broadcast_to_all(message)
    
    async def notify_optimization_progress(self, progress: int, generation: int, fitness: float):
        """Notify admins about optimization progress"""
        message = {
            "type": "optimization_progress",
            "progress": progress,
            "generation": generation,
            "fitness": fitness,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.broadcast_to_admins(message)
    
    async def notify_teacher_leave_update(self, faculty_id: str, leave_details: dict):
        """Notify about teacher leave and timetable changes"""
        message = {
            "type": "teacher_leave_update",
            "faculty_id": faculty_id,
            "leave_details": leave_details,
            "message": "Teacher leave has been processed and timetable updated",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.broadcast_to_all(message)
    
    async def notify_system_maintenance(self, maintenance_details: dict):
        """Notify all users about system maintenance"""
        message = {
            "type": "system_maintenance",
            "details": maintenance_details,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.broadcast_to_all(message)
    
    def get_connection_stats(self) -> dict:
        """Get connection statistics"""
        stats = {
            "total_connections": sum(len(connections) for connections in self.active_connections.values()),
            "by_user_type": {
                user_type: len(connections) 
                for user_type, connections in self.active_connections.items()
            },
            "active_sessions": len(self.user_sessions)
        }
        return stats
    
    def get_connected_users(self, user_type: str = None) -> List[str]:
        """Get list of connected users"""
        if user_type:
            return list(self.active_connections.get(user_type, {}).keys())
        
        connected_users = []
        for ut, connections in self.active_connections.items():
            for user_id in connections.keys():
                connected_users.append(f"{ut}:{user_id}")
        
        return connected_users
    
    async def send_heartbeat(self):
        """Send heartbeat to all connections to keep them alive"""
        heartbeat_message = {
            "type": "heartbeat",
            "timestamp": datetime.utcnow().isoformat(),
            "server_status": "online"
        }
        
        await self.broadcast_to_all(heartbeat_message)
    
    async def handle_client_message(self, websocket: WebSocket, user_type: str, user_id: str, message: str):
        """Handle messages from clients"""
        try:
            data = json.loads(message)
            message_type = data.get('type')
            
            if message_type == 'ping':
                # Respond to ping with pong
                await self.send_personal_message({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                }, user_type, user_id)
            
            elif message_type == 'subscribe_to_batch' and user_type == 'student':
                # Handle batch subscription for students
                batch_id = data.get('batch_id')
                if batch_id:
                    # Store subscription info (you might want to use a proper subscription manager)
                    logger.info(f"Student {user_id} subscribed to batch {batch_id}")
            
            elif message_type == 'get_status':
                # Send current status
                stats = self.get_connection_stats()
                await self.send_personal_message({
                    "type": "status",
                    "stats": stats,
                    "timestamp": datetime.utcnow().isoformat()
                }, user_type, user_id)
            
            else:
                logger.warning(f"Unknown message type from {user_type}:{user_id}: {message_type}")
        
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON message from {user_type}:{user_id}: {message}")
        except Exception as e:
            logger.error(f"Error handling message from {user_type}:{user_id}: {e}")

# Create global WebSocket manager instance
websocket_manager = WebSocketManager()
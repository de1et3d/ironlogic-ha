#!/usr/bin/env python3
"""
IronLogic WebSocket Debug Server - send read_cards immediately after power_on
"""

import asyncio
import websockets
import json
from datetime import datetime

async def handle_connection(websocket):
    print("Client connected")
    try:
        async for message in websocket:
            print(f"Received: {message}")
            
            data = json.loads(message)
            messages = data.get("messages", [])
            
            response_messages = []
            for msg in messages:
                operation = msg.get("operation")
                msg_id = msg.get("id")
                
                if operation == "power_on":
                    response_messages.append({
                        "id": msg_id + 1,
                        "operation": "set_active",
                        "active": 1,
                        "online": 1
                    })
                    response_messages.append({
                        "id": msg_id + 2,
                        "operation": "read_cards"
                    })
                    print("Sent set_active and read_cards")
                
                elif operation == "ping":
                    response_messages.append({
                        "id": msg_id + 1,
                        "operation": "read_cards"
                    })
                    print("Sent read_cards on ping")
            
            response = {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "interval": 10,
                "messages": response_messages,
            }
            
            await websocket.send(json.dumps(response))
            print(f"Response sent: {response}")
            
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")

async def main():
    async with websockets.serve(handle_connection, "0.0.0.0", 8000):
        print("Starting IronLogic WebSocket debug server on port 8000...")
        print("Point your controller to: ws://<IP>:8000/")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
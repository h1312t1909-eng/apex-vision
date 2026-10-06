import { useEffect, useRef, useState, useCallback } from 'react';

export interface WebSocketEvent {
  event_type: 'recognition' | 'attendance_update' | 'spoof_alert' | 'camera_status';
  classroom_id: number;
  period_id?: number | null;
  timestamp: string;
  data: any;
}

export function useClassroomWebSocket(classroomId: number | null, onMessageReceived?: (event: WebSocketEvent) => void) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (!classroomId) return;

    const wsUrl = `ws://localhost:8000/ws/classrooms/${classroomId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const payload: WebSocketEvent = JSON.parse(event.data);
        if (onMessageReceived) {
          onMessageReceived(payload);
        }
      } catch (err) {
        console.error('[WS Parse Error]', err);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      // Auto-reconnect after 3 seconds
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, 3000);
    };

    ws.onerror = (err) => {
      console.error('[WS Error]', err);
      ws.close();
    };
  }, [classroomId, onMessageReceived]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { isConnected };
}

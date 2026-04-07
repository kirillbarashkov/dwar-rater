import { useState, useEffect, useRef } from 'react';
import type { Clan, ChatRoom, ChatMessage } from '../../types/clan';
import { getClans, getRooms, getMessages, sendMessage } from '../../api/clans';
import './ClanChat.css';

interface ClanChatProps {
  onClose: () => void;
}

export function ClanChat({ onClose }: ClanChatProps) {
  const [clans, setClans] = useState<Clan[]>([]);
  const [selectedClan, setSelectedClan] = useState<Clan | null>(null);
  const [rooms, setRooms] = useState<ChatRoom[]>([]);
  const [selectedRoom, setSelectedRoom] = useState<ChatRoom | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    getClans().then(setClans).catch(() => setClans([]));
  }, []);

  useEffect(() => {
    if (!selectedClan) return;
    getRooms(selectedClan.id).then((r) => {
      setRooms(r);
      if (r.length > 0) setSelectedRoom(r[0]);
    }).catch(() => setRooms([]));
  }, [selectedClan]);

  useEffect(() => {
    if (!selectedClan || !selectedRoom) return;
    const load = () => {
      getMessages(selectedClan.id, selectedRoom.id, { limit: 50 })
        .then(setMessages)
        .catch(() => {});
    };
    load();
    pollRef.current = window.setInterval(load, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [selectedClan, selectedRoom]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !selectedClan || !selectedRoom) return;
    try {
      const msg = await sendMessage(selectedClan.id, selectedRoom.id, input.trim());
      setMessages((prev) => [...prev, msg]);
      setInput('');
    } catch {
      // ignore
    }
  };

  return (
    <div className="clan-chat">
      <div className="cc-header">
        <h3>Клановый чат</h3>
        <button className="cc-close" onClick={onClose}>×</button>
      </div>

      {clans.length === 0 ? (
        <p className="cc-empty">Нет кланов</p>
      ) : (
        <>
          <div className="cc-clan-select">
            {clans.map((c) => (
              <button
                key={c.id}
                className={`cc-clan-btn ${selectedClan?.id === c.id ? 'active' : ''}`}
                onClick={() => setSelectedClan(c)}
              >
                {c.name}
              </button>
            ))}
          </div>

          {selectedClan && rooms.length > 0 && (
            <div className="cc-rooms">
              {rooms.map((r) => (
                <button
                  key={r.id}
                  className={`cc-room-btn ${selectedRoom?.id === r.id ? 'active' : ''}`}
                  onClick={() => { setSelectedRoom(r); setMessages([]); }}
                >
                  {r.name}
                </button>
              ))}
            </div>
          )}

          <div className="cc-messages">
            {messages.length === 0 ? (
              <p className="cc-no-messages">Нет сообщений</p>
            ) : (
              messages.map((m) => (
                <div key={m.id} className="cc-message">
                  <span className="cc-msg-user">{m.username}</span>
                  <span className="cc-msg-text">{m.content}</span>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          <form className="cc-input-form" onSubmit={handleSend}>
            <input
              className="cc-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Сообщение..."
              disabled={!selectedRoom}
            />
            <button type="submit" className="btn btn-primary btn-sm" disabled={!input.trim() || !selectedRoom}>
              →
            </button>
          </form>
        </>
      )}
    </div>
  );
}

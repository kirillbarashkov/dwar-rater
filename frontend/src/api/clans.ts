import apiClient from './client';
import type { Clan, ClanMember, ChatRoom, ChatMessage } from '../types/clan';

export async function getClans(): Promise<Clan[]> {
  const response = await apiClient.get('/api/clans');
  return response.data;
}

export async function createClan(name: string): Promise<{ id: number; name: string }> {
  const response = await apiClient.post('/api/clans', { name });
  return response.data;
}

export async function getMembers(clanId: number): Promise<ClanMember[]> {
  const response = await apiClient.get(`/api/clans/${clanId}/members`);
  return response.data;
}

export async function addMember(clanId: number, userId: number, role?: string): Promise<void> {
  await apiClient.post(`/api/clans/${clanId}/members`, { user_id: userId, role });
}

export async function removeMember(clanId: number, userId: number): Promise<void> {
  await apiClient.delete(`/api/clans/${clanId}/members/${userId}`);
}

export async function getRooms(clanId: number): Promise<ChatRoom[]> {
  const response = await apiClient.get(`/api/clans/${clanId}/rooms`);
  return response.data;
}

export async function createRoom(clanId: number, name: string): Promise<{ id: number; name: string }> {
  const response = await apiClient.post(`/api/clans/${clanId}/rooms`, { name });
  return response.data;
}

export async function getMessages(clanId: number, roomId: number, params?: { limit?: number; before?: number }): Promise<ChatMessage[]> {
  const response = await apiClient.get(`/api/clans/${clanId}/rooms/${roomId}/messages`, { params });
  return response.data;
}

export async function sendMessage(clanId: number, roomId: number, content: string): Promise<ChatMessage> {
  const response = await apiClient.post(`/api/clans/${clanId}/rooms/${roomId}/messages`, { content });
  return response.data;
}

export async function deleteMessage(clanId: number, roomId: number, msgId: number): Promise<void> {
  await apiClient.delete(`/api/clans/${clanId}/rooms/${roomId}/messages/${msgId}`);
}

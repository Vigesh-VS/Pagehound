import { collection, deleteDoc, doc, getDoc, limit, onSnapshot, orderBy, query, serverTimestamp, setDoc } from 'firebase/firestore'
import { db } from './firebase'

export type StoredMsg = { role: 'user' | 'assistant'; text: string; labels?: string[]; file?: string }
export type Chat = { id: string; title: string; fileName: string; files: string[]; docId?: string; messages: StoredMsg[]; updatedAt: number }

const chatsOf = (uid: string) => collection(db!, 'users', uid, 'chats')

export const newChatId = (uid: string) => doc(chatsOf(uid)).id

export function subscribeChats(uid: string, onChange: (chats: Chat[]) => void) {
  if (!db) {
    onChange([])
    return () => {}
  }
  const recent = query(chatsOf(uid), orderBy('updatedAt', 'desc'), limit(30))
  return onSnapshot(
    recent,
    (snapshot) =>
      onChange(
        snapshot.docs.map((item) => {
          const data = item.data({ serverTimestamps: 'estimate' })
          return {
            id: item.id,
            title: data.title ?? 'Untitled chat',
            fileName: data.fileName ?? '',
            files: data.files ?? (data.fileName ? [data.fileName] : []),
            docId: data.docId ?? undefined,
            messages: data.messages ?? [],
            updatedAt: data.updatedAt?.toMillis?.() ?? 0,
          }
        }),
      ),
    (error) => {
      console.warn('Could not load chat history', error)
      onChange([])
    },
  )
}

export async function saveChat(uid: string, chat: Omit<Chat, 'updatedAt'>) {
  if (!db) return
  await setDoc(doc(chatsOf(uid), chat.id), {
    title: chat.title,
    fileName: chat.fileName,
    files: chat.files,
    docId: chat.docId ?? null,
    messages: chat.messages,
    updatedAt: serverTimestamp(),
  })
}

export async function removeChat(uid: string, id: string) {
  if (!db) return
  await deleteDoc(doc(chatsOf(uid), id))
}

export async function getChat(uid: string, id: string): Promise<Chat | null> {
  if (!db) return null
  const item = await getDoc(doc(chatsOf(uid), id))
  if (!item.exists()) return null
  const data = item.data({ serverTimestamps: 'estimate' })
  return {
    id: item.id,
    title: data.title ?? 'Untitled chat',
    fileName: data.fileName ?? '',
    files: data.files ?? (data.fileName ? [data.fileName] : []),
    docId: data.docId ?? undefined,
    messages: data.messages ?? [],
    updatedAt: data.updatedAt?.toMillis?.() ?? 0,
  }
}

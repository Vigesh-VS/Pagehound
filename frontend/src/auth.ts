import { useEffect, useState } from 'react'
import { onAuthStateChanged, signInWithPopup, signOut as firebaseSignOut } from 'firebase/auth'
import { auth, googleProvider } from './firebase'

export type User = { uid: string; name: string; email: string; photo?: string }

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(!auth)

  useEffect(() => {
    if (!auth) return
    return onAuthStateChanged(auth, (account) => {
      setUser(
        account
          ? { uid: account.uid, name: account.displayName || account.email || 'Signed in', email: account.email || '', photo: account.photoURL || undefined }
          : null,
      )
      setReady(true)
    })
  }, [])

  async function signIn() {
    if (!auth) throw new Error('Firebase is not configured. Add your settings to frontend/.env and restart npm run dev.')
    try {
      await signInWithPopup(auth, googleProvider)
    } catch (e) {
      const code = (e as { code?: string }).code
      if (code === 'auth/popup-closed-by-user' || code === 'auth/cancelled-popup-request') throw new Error('Sign-in was cancelled.')
      if (code === 'auth/popup-blocked') throw new Error('Your browser blocked the sign-in popup. Allow popups for this site and try again.')
      if (code === 'auth/unauthorized-domain') throw new Error('This website address is not authorized in Firebase yet.')
      throw new Error('Sign-in failed. Please try again.')
    }
  }

  const signOut = async () => {
    if (auth) await firebaseSignOut(auth)
  }

  const getToken = async () => (auth?.currentUser ? auth.currentUser.getIdToken() : undefined)

  return { user, ready, signIn, signOut, getToken }
}

import { lazy, Suspense, useEffect, useState } from 'react'
import App from './App'
const Contribute = lazy(() => import('./Contribute'))

export default function Root() {
  const [path, setPath] = useState(window.location.pathname)
  const [back, setBack] = useState('/')

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  function go(to: string) {
    window.history.pushState({}, '', to)
    setPath(to)
    window.scrollTo(0, 0)
  }

  const onContribute = path === '/contribute'

  return (
    <>
      <div hidden={onContribute}>
        <App onContribute={() => { setBack(window.location.pathname); go('/contribute') }} />
      </div>
      {onContribute && (
        <Suspense fallback={null}>
          <Contribute onBack={() => go(back === '/contribute' ? '/' : back)} />
        </Suspense>
      )}
    </>
  )
}

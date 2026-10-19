import { useEffect } from 'react'

export default function HomamRedirect() {
  useEffect(() => {
    if (window.location.protocol === 'file:') {
      window.location.replace('../index.html#homams')
      return
    }
    window.location.href = '/homam'
  }, [])
  return (
    <div className="homam-loading">
      <p>Returning to Sacred Homams…</p>
    </div>
  )
}

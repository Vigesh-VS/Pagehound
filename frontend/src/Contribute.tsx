import { useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'

const UPI_ID = 'thevigesh17@oksbi'
const PAYEE = 'Vigesh V S'

export const UPI_LINK = `upi://pay?pa=${UPI_ID}&pn=${encodeURIComponent(PAYEE)}&cu=INR`

const onPhone = () => /android|iphone|ipad|ipod/i.test(navigator.userAgent)

export default function Contribute({ onBack }: { onBack: () => void }) {
  const [hint, setHint] = useState(false)

  return (
    <div className="contribute">
      <div className="pay-card">
        <h2>Contribute</h2>
        <div className="qr">
          <QRCodeSVG value={UPI_LINK} size={220} level="M" bgColor="#ffffff" fgColor="#000000" />
        </div>
        <p className="pay-name">{PAYEE}</p>
        <p className="pay-id">UPI ID: {UPI_ID}</p>
        <a
          className="brut"
          href={UPI_LINK}
          onClick={(e) => {
            if (!onPhone()) {
              e.preventDefault()
              setHint(true)
            }
          }}
        >
          Pay with UPI
        </a>
        <p className="pay-note">Scan to pay with any UPI app</p>
        {hint && <p className="pay-hint">UPI apps open on phones. Scan the QR with your phone, or open this page on your phone.</p>}
      </div>
      <button className="brut outline" onClick={onBack}>← Back</button>
    </div>
  )
}

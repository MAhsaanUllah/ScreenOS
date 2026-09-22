import { useEffect, useRef, useState } from 'react'

const STATES = [
  { name: 'idle', body: 'M50,10 C75,10 90,25 90,50 C90,75 75,90 50,90 C25,90 10,75 10,50 C10,25 25,10 50,10Z', eyeL: [38, 42], eyeR: [62, 42] },
  { name: 'blink', body: 'M50,10 C75,10 90,25 90,50 C90,75 75,90 50,90 C25,90 10,75 10,50 C10,25 25,10 50,10Z', eyeL: [38, 44], eyeR: [62, 44], eyeH: 1.5 },
  { name: 'wide', body: 'M50,8 C78,8 92,22 92,50 C92,78 78,92 50,92 C22,92 8,78 8,50 C8,22 22,8 50,8Z', eyeL: [36, 40], eyeR: [64, 40] },
  { name: 'squint', body: 'M50,12 C72,12 88,28 88,50 C88,72 72,88 50,88 C28,88 12,72 12,50 C12,28 28,12 50,12Z', eyeL: [40, 44], eyeR: [60, 44], eyeH: 2.5 },
]

function lerp(a, b, t) { return a + (b - a) * t }
function clamp(v, min, max) { return Math.min(Math.max(v, min), max) }

export default function BlobMascot({ size = 100, className = '' }) {
  const svgRef = useRef(null)
  const [mouse, setMouse] = useState({ x: 0.5, y: 0.5 })
  const [blink, setBlink] = useState(false)
  const smoothMouse = useRef({ x: 0.5, y: 0.5 })
  const raf = useRef(null)
  const stateIdx = useRef(0)
  const transition = useRef(0)

  useEffect(() => {
    function onMove(e) {
      const x = clamp(e.clientX / window.innerWidth, 0, 1)
      const y = clamp(e.clientY / window.innerHeight, 0, 1)
      setMouse({ x, y })
    }
    window.addEventListener('mousemove', onMove, { passive: true })
    return () => window.removeEventListener('mousemove', onMove)
  }, [])

  // Blink timer
  useEffect(() => {
    const t = setInterval(() => {
      setBlink(true)
      setTimeout(() => setBlink(false), 180)
    }, 3000 + Math.random() * 2000)
    return () => clearInterval(t)
  }, [])

  // State morph timer
  useEffect(() => {
    const t = setInterval(() => {
      stateIdx.current = (stateIdx.current + 1) % STATES.length
      transition.current = 0
    }, 4000)
    return () => clearInterval(t)
  }, [])

  // Animation loop
  useEffect(() => {
    let last = performance.now()
    function tick(now) {
      const dt = Math.min((now - last) / 1000, 0.1)
      last = now

      // Smooth eye follow (spring physics)
      const springK = 8
      const damping = 0.85
      const dx = mouse.x - smoothMouse.current.x
      const dy = mouse.y - smoothMouse.current.y
      smoothMouse.current.x += dx * springK * dt
      smoothMouse.current.y += dy * springK * dt

      // Transition progress
      transition.current = Math.min(transition.current + dt * 2.5, 1)

      // Update SVG
      if (svgRef.current) {
        const curr = STATES[stateIdx.current]
        const next = STATES[(stateIdx.current + 1) % STATES.length]
        const t = transition.current

        // Interpolate eye positions
        const eyeLX = lerp(curr.eyeL[0], next.eyeL[0], t)
        const eyeLY = lerp(curr.eyeL[1], next.eyeL[1], t)
        const eyeRX = lerp(curr.eyeR[0], next.eyeR[0], t)
        const eyeRY = lerp(curr.eyeR[1], next.eyeR[1], t)

        // Gaze offset from cursor (max ±4px)
        const gazeX = (smoothMouse.current.x - 0.5) * 8
        const gazeY = (smoothMouse.current.y - 0.5) * 6

        const eyeL = svgRef.current.getElementById('eye-l')
        const eyeR = svgRef.current.getElementById('eye-r')
        if (eyeL && eyeR) {
          const eyeH = blink ? 1.5 : (curr.eyeH || 3.5)
          eyeL.setAttribute('cx', eyeLX + gazeX)
          eyeL.setAttribute('cy', eyeLY + gazeY)
          eyeL.setAttribute('rx', 3.5)
          eyeL.setAttribute('ry', eyeH)
          eyeR.setAttribute('cx', eyeRX + gazeX)
          eyeR.setAttribute('cy', eyeRY + gazeY)
          eyeR.setAttribute('rx', 3.5)
          eyeR.setAttribute('ry', eyeH)
        }

        // Interpolate body path
        const body = svgRef.current.getElementById('body')
        if (body) body.setAttribute('d', curr.body)
      }

      raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf.current)
  }, [mouse, blink])

  return (
    <svg
      ref={svgRef}
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={className}
      style={{ overflow: 'visible' }}
    >
      <defs>
        <radialGradient id="blob-grad" cx="40%" cy="35%" r="60%">
          <stop offset="0%" stopColor="#7e9cf7" />
          <stop offset="100%" stopColor="#2563eb" />
        </radialGradient>
        <filter id="blob-shadow">
          <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#2563eb" floodOpacity="0.25" />
        </filter>
      </defs>
      <path
        id="body"
        d={STATES[0].body}
        fill="url(#blob-grad)"
        filter="url(#blob-shadow)"
        style={{ transition: 'd 0.4s ease-out' }}
      />
      <ellipse id="eye-l" cx="38" cy="42" rx="3.5" ry="3.5" fill="white" />
      <ellipse id="eye-r" cx="62" cy="42" rx="3.5" ry="3.5" fill="white" />
    </svg>
  )
}

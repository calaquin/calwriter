import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCreateBookWizard } from '../api/hooks'
import { ApiError } from '../api/client'

const EXTRA_OPTIONS = ['Characters', 'Factions', 'Locations']

export default function WizardPage() {
  const navigate = useNavigate()
  const wizard = useCreateBookWizard()
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [chapters, setChapters] = useState('Chapters')
  const [color, setColor] = useState('#dddddd')
  const [extras, setExtras] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  function toggleExtra(name: string) {
    setExtras((prev) => (prev.includes(name) ? prev.filter((e) => e !== name) : [...prev, name]))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const book = await wizard.mutateAsync({ title, author, chapters, color, extras })
      navigate(`/folders/${book.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create book')
    }
  }

  return (
    <div>
      <h1>Create a Book</h1>
      {error && (
        <ul className="flashes">
          <li>{error}</li>
        </ul>
      )}
      <form onSubmit={handleSubmit}>
        <p>
          <label>
            Book title:
            <br />
            <input type="text" placeholder="Book title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
        </p>
        <p>
          <label>
            Author:
            <br />
            <input type="text" placeholder="Author name" value={author} onChange={(e) => setAuthor(e.target.value)} />
          </label>
        </p>
        <p>
          <label>
            Chapters sub-folder:
            <br />
            <input type="text" value={chapters} onChange={(e) => setChapters(e.target.value)} />
          </label>
        </p>
        <p>
          <label>
            Book color:
            <br />
            <input type="color" value={color} onChange={(e) => setColor(e.target.value)} />
          </label>
        </p>
        <p>Additional sub-folders:</p>
        {EXTRA_OPTIONS.map((name) => (
          <p key={name}>
            <label>
              <input type="checkbox" checked={extras.includes(name)} onChange={() => toggleExtra(name)} /> {name}
            </label>
          </p>
        ))}
        <button type="submit">Create Book</button>
      </form>
    </div>
  )
}

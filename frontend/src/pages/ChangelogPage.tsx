import { useChangelog } from '../api/hooks'

export default function ChangelogPage() {
  const { data, isLoading } = useChangelog()

  return (
    <div>
      <h1>Changelog</h1>
      {isLoading && <p>Loading...</p>}
      {data && <pre className="changelog">{data.content}</pre>}
    </div>
  )
}

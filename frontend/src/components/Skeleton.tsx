/** Muted placeholder bars. The shimmer stops under prefers-reduced-motion. */
export function Skeleton({ width = '100%' }: { width?: string }) {
  return <span className="skeleton" style={{ width }} aria-hidden="true" />
}

/** Several placeholder rows, for a list or table that is still loading. */
function SkeletonRows({ count = 4 }: { count?: number }) {
  return (
    <div className="skeleton-stack" role="status" aria-label="Loading">
      {Array.from({ length: count }, (_, index) => (
        <div className="skeleton-row" key={index}>
          <Skeleton width="52%" />
          <Skeleton width="14%" />
          <Skeleton width="18%" />
        </div>
      ))}
    </div>
  )
}

export default SkeletonRows

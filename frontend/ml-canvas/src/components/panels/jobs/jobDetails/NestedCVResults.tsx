type NestedReport = {
  status: 'nested_cv'; outer_folds: number; inner_folds: number;
  scoring_metric: string; mean_score: number; std_score: number; total_trials: number;
  folds: { fold: number; inner_best_score: number; outer_score: number; best_params: Record<string, unknown> }[];
};

/** Read current evidence while leaving legacy diagnostic job results unchanged. */
export function nestedReport(result: Record<string, unknown>): NestedReport | null {
  const metrics = result.metrics as Record<string, unknown> | undefined;
  const raw = (metrics?.nested_cv ?? result.nested_cv) as Partial<NestedReport> | undefined;
  if (!raw || raw.status !== 'nested_cv' || !Array.isArray(raw.folds)
    || !Number.isFinite(raw.mean_score) || !Number.isFinite(raw.std_score)) return null;
  return raw as NestedReport;
}

/** Outer evaluation remains separate from the final model's inner-search optimum. */
export function NestedCVResults({ result }: { result: Record<string, unknown> }) {
  const report = nestedReport(result);
  if (!report) return null;
  return (
    <section className="space-y-2">
      <h4 className="text-sm font-medium text-gray-700 dark:text-gray-200">Nested CV evaluation</h4>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        {report.outer_folds} outer folds · {report.inner_folds} inner folds · {report.scoring_metric}
        {' · '}Outer mean: {report.mean_score.toFixed(4)} ± {report.std_score.toFixed(4)}
      </p>
      <p className="text-xs text-gray-500 dark:text-gray-400">Each outer score evaluates an independent search on untouched rows. Higher scores are better; negative loss scores remain negative.</p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left">
          <thead><tr><th scope="col">Fold</th><th scope="col">Inner best score</th><th scope="col">Outer score</th><th scope="col">Selected parameters</th></tr></thead>
          <tbody>{report.folds.map((fold) => (
            <tr key={fold.fold} className="border-t border-gray-200 dark:border-gray-700">
              <td className="py-2">{fold.fold}</td><td>{fold.inner_best_score.toFixed(4)}</td><td>{fold.outer_score.toFixed(4)}</td>
              <td className="font-mono">{JSON.stringify(fold.best_params)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}

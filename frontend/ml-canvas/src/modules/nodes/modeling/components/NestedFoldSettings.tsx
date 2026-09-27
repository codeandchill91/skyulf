import { ValidationField } from '../../../../components/shared/ValidationField';
import { numericDraft, numericInputValue } from '../../../../core/utils/numericValidation';

/** Inner tuning folds are independent of outer evaluation and ensemble stacking folds. */
export function NestedFoldSettings({ fieldId, outerFolds, innerFolds, onChange }: {
  fieldId: string;
  outerFolds: number;
  innerFolds: number | undefined;
  onChange: (value: number) => void;
}) {
  const defaultInner = outerFolds > 2 ? Math.min(3, outerFolds - 1) : 2;
  return (
    <div className="space-y-2">
      <label htmlFor={`${fieldId}-cv-inner-folds`} className="block text-xs text-gray-500">Inner folds</label>
      <ValidationField field="cv_inner_folds">
        <input id={`${fieldId}-cv-inner-folds`} type="number" min={2}
          value={numericInputValue(innerFolds, defaultInner)}
          onChange={(event) => { onChange(numericDraft(event.target.value)); }}
          className="w-full border border-gray-300 dark:border-gray-600 rounded p-1.5 text-sm bg-white dark:bg-gray-800 dark:text-gray-100" />
      </ValidationField>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        Each outer fold runs a fresh search using these inner folds. A separate final search trains the saved model.
        Search budgets apply to each inner search and the final search.
      </p>
    </div>
  );
}

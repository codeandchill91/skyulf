import { expect, it } from 'vitest';
import { buildBaseTuningConfig, buildFixedTrainingParams } from './training';

/** Both model routes must retain the separate inner-fold choice without adding defaults. */
it.each([buildBaseTuningConfig, buildFixedTrainingParams])('forwards explicit nested folds', (build) => {
  expect(build({ cv_type: 'nested_cv', cv_folds: 5, cv_inner_folds: 3 })).toMatchObject({ cv_type: 'nested_cv', cv_folds: 5, cv_inner_folds: 3 });
  expect(build({ cv_type: 'k_fold', cv_folds: 5 })).not.toHaveProperty('cv_inner_folds');
});

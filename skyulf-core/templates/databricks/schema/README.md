# Maintaining the Bundle wizard

Edit the topic files here, then regenerate the schema from the repository root:

```sh
python skyulf-core/templates/databricks/build_schema.py
python skyulf-core/templates/databricks/build_schema.py --check
```

The script uses only Python's standard library and also works from another working
directory when invoked by its path. Commit the topic files and the generated
`databricks_template_schema.json` together. Pre-commit and CI reject stale output.
Bundle users continue to run `databricks bundle init` normally; no build step is
required for them. These maintenance files sit outside `template/`, so they are
not copied into generated projects.

## Where to edit

| File | Questions/settings |
| --- | --- |
| `metadata.json` | Root schema fields, including the welcome message |
| `project.json` | Layout, project, engine, task, source, columns and snapshot |
| `training.json` | Split, training windows, sampling and input limits |
| `time_columns.json` | Event-time column parsing and timezone |
| `label_availability.json` | Label availability and its timestamp parsing |
| `models.json` | Classification/regression model selection and parameters |
| `tuning.json` | Search strategy, space, metric, resources and threshold tuning |
| `cross_validation.json` | Ordinary/nested folds, group/time splits and seed |
| `scheduling.json` | Training and scoring schedules |
| `scoring.json` | Single-model prediction source/output, promotion and quality |
| `model_set.json` | Set name, promotion, outputs/views and source-change policy |
| `deployment.json` | Compute, cluster policy and cost tags |

Each topic file is a JSON object whose keys are the existing wizard field names:

```json
{
  "project_name": {
    "order": 1,
    "type": "string",
    "default": "skyulf_local",
    "description": "Project folder and Bundle name"
  }
}
```

The builder merges every `schema/*.json` topic except `metadata.json`, places its
fields under `properties`, and sorts them by their explicit `order`. Keep orders
unique and keep referenced questions earlier than their dependents. A
`skip_prompt_if` condition can reference a field from another topic; it retains
the same meaning in the merged schema. Duplicate names within or between files
fail instead of overwriting a definition. To add a topic, create another JSON
file here; no list in the builder needs editing.

The large root JSON is generated output. Make future edits here, not there.

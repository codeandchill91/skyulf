# Skyulf Landing Iterations Design

## Goal

Create three complete, standalone Skyulf landing-page iterations for customer evaluation:

1. Twin Tracks
2. Two Voices
3. Private Workflow

The iterations must present Skyulf Platform and `skyulf-core` as equal, complementary entry paths. They must use real product capabilities and screenshots without fabricated statistics, customers, testimonials, benchmarks, or simulated product experiences.

## Shared Product Story

Every iteration must make these facts clear:

- Skyulf connects data exploration, pipeline creation, training, experiment comparison, model registry, deployment, inference, and drift monitoring.
- Customers can use the self-hosted visual platform or the independent `skyulf-core` Python package.
- Visual pipelines can be exported as full or compact Jupyter notebooks.
- The hosted demo is for evaluation; the platform can run locally or on customer-controlled infrastructure.
- `skyulf-core` can be installed and used without the web platform.

The two primary actions are:

- Open Skyulf Platform at `https://api.skyulf.com`.
- Install or inspect `skyulf-core` through PyPI.

## Iteration 1: Twin Tracks

### Design Contract

Twin Tracks uses a direct split-screen composition. The left side represents the visual platform, and the right side represents the Python engine. Both receive equal prominence and converge into one shared workflow.

### Visual System

- Warm off-white visual side.
- Saturated blue Python side.
- Orange circular junction representing the shared workflow.
- Large, direct typography with minimal decorative material.
- Structured black-and-white sections below the hero.

### Customer Journey

1. Immediately understand the visual and Python choices.
2. See how both paths converge into one lifecycle.
3. Review real screenshots.
4. Compare Platform and `skyulf-core`.
5. Resolve deployment, portability, and ownership questions.
6. Choose either the live demo or the Python package.

## Iteration 2: Two Voices

### Design Contract

Two Voices presents the customer's competing needs as a typographic conversation:

- "I need to see the workflow."
- "I need to own the code."

Skyulf resolves the tension without treating either preference as secondary.

### Visual System

- Warm paper background.
- Red visual-platform voice.
- Blue Python voice.
- Expressive editorial typography with intentionally different scale and direction for each speaker.
- Real product screenshots staged as evidence rather than embedded in generic cards.

### Customer Journey

1. Recognize the visual-versus-code tension.
2. Understand each interface through its own voice.
3. See how the interfaces exchange responsibilities.
4. Review real canvas and EDA evidence.
5. Confirm ownership, portability, continuity, and self-hosting.
6. Select the visual or Python entry path.

## Iteration 3: Private Workflow

### Design Contract

Private Workflow is the most conventional customer-facing direction. It leads with infrastructure control, portability, and deployment flexibility rather than visual experimentation.

### Visual System

- White background with strong yellow accents.
- High-contrast, sales-ready typography.
- Clear platform screenshots.
- Direct assurance sections for infrastructure, portability, and Python independence.
- Restrained component system suitable for technical customers and decision-makers.

### Customer Journey

1. Understand that Skyulf can run on customer-controlled infrastructure.
2. See the complete workflow from data to monitoring.
3. Choose the full platform or standalone Python engine.
4. Review real experiment and product evidence.
5. Resolve infrastructure and deployment questions.
6. Try the platform or install `skyulf-core`.

## Shared Content Architecture

Each site must include:

- Navigation with product, workflow, interface, and FAQ routes.
- Customer-focused hero with both primary entry actions.
- Complete product lifecycle explanation.
- Real screenshots from `static/img/`.
- Separate Platform and `skyulf-core` explanations.
- Self-hosting, notebook-export, and ownership proof.
- FAQ covering interface choice, deployment, and data control.
- Final dual CTA.
- Footer with product and license context where appropriate.

## Files and Review Hub

Implementation will create:

- `redesign/iteration-1/index.html` for Twin Tracks.
- `redesign/iteration-2/index.html` for Two Voices.
- `redesign/iteration-3/index.html` for Private Workflow.
- `redesign/index.html` as a simple review hub linking only these three iterations.

No rejected concepts or unused iteration directories will remain.

## Responsive and Accessibility Requirements

- Semantic landmarks and heading order.
- Keyboard-accessible navigation and links.
- Visible focus states.
- WCAG AA text contrast.
- Responsive reflow for split layouts, dialogue composition, and workflow grids.
- Reduced-motion support for any authored animation.
- Descriptive image alternative text.
- No interaction that duplicates the hosted live demo.

## Verification

- Confirm all four HTML files load without missing local assets.
- Inspect desktop and mobile renders in one bounded screenshot pass.
- Run the Impeccable detector once after the final UI edits.
- Confirm every factual capability against `PRODUCT.md` and repository documentation.
- Confirm only the three approved iteration directories and review hub remain.

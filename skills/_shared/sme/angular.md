---
name: angular
description: Angular architecture do's and don'ts
match: ["@angular/core", "@angular/cli", "angular"]
see_also: ["platform-native#html-elements", "platform-native#css-capabilities"]
---
## Do
- Use standalone components, directives, and pipes; avoid declaring them in NgModules.
- Use signals (`signal`, `computed`, `effect`) for local component state; prefer the `inject()` function over constructor injection.
- Set `changeDetection: ChangeDetectionStrategy.OnPush` on components.
- Use typed reactive forms (`FormGroup`/`FormControl` with explicit types) for non-trivial input.
- Clean up subscriptions with `takeUntilDestroyed()` or the `async` pipe; prefer the `async` pipe over manual subscription.
- Lazy-load feature routes with `loadComponent` / `loadChildren`.

## Don't
- Don't put logic in templates beyond simple expressions; move it to the component or a pipe.
- Don't use `any`; type inputs, outputs, and service results.
- Don't subscribe to a long-lived observable without a teardown path; a single-shot finite observable (e.g. an `HttpClient` request) completes on its own.
- Don't mutate `@Input()` values; treat inputs as read-only.
- Don't reach into the DOM with `ElementRef.nativeElement` when a binding or directive will do.

## Patterns
- Smart/presentational split: container components own data and effects; presentational components take inputs and emit outputs.
- One responsibility per service; provide app-wide singletons with `providedIn: 'root'`.
- Co-locate a component's template, styles, and spec with the component.

## Review checklist
- [ ] ng.1 — No `any` in changed component/service signatures.
- [ ] ng.2 — Every new component declares `ChangeDetectionStrategy.OnPush`.
- [ ] ng.3 — No `.subscribe()` on a long-lived or multi-emission observable without `takeUntilDestroyed()`, an `async` pipe, or an explicit unsubscribe — a single-shot finite observable (e.g. an `HttpClient` request) that completes on first emission is exempt.
- [ ] ng.4 — New components/directives/pipes are `standalone`, not added to an NgModule's `declarations`.
- [ ] ng.5 — No business logic embedded in a template expression.
- [ ] ng.6 — No date/color/range/time-picker dependency where a native `<input type=…>` covers it (see platform-native).

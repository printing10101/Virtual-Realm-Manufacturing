// Supported Vue Component Types
// This file provides explicit type declarations for Vue components that
// may not be auto-detected by the Vue language server.

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  // eslint（@typescript-eslint/ban-types）不允许裸 `{}`，语义等价改写为 Record<string, never>
  const component: DefineComponent<
    Record<string, never>,
    Record<string, never>,
    any
  >;
  export default component;
}

// Cutting Experience Dashboard Component Declaration

// Explicit declaration to avoid TS7016 errors
declare module "@/components/experience/CuttingExperienceDashboard.vue" {
  import type { DefineComponent } from "vue";

  interface CuttingExperienceDashboardProps {
    t?: (key: string) => string;
    store?: unknown;
  }

  const CuttingExperienceDashboard: DefineComponent<CuttingExperienceDashboardProps>;
  export default CuttingExperienceDashboard;
}

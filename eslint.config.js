export default [
  {
    ignores: [
      "packages/auth/src/**",
      "packages/utils/src/**",
      "packages/api-client/src/**",
      "packages/dashboard/src/**",
      "packages/ui/src/**",
      "apps/whatsapp-assistant/src/**",
      "apps/control-panel/src/**",
      "apps/dashboard/src/**",
      "dist/**",
      "node_modules/**",
    ],
  },
  {
    files: ["**/*.{js,jsx}"],
    rules: {},
  },
];

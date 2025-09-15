import { defineConfig } from 'cypress'

export default defineConfig({
  e2e: {
    baseUrl: 'http://localhost:3000',
    specPattern: 'cypress/e2e/**/*.cy.ts',
    supportFile: 'cypress/support/e2e.ts',
    video: false,
    retries: {
      runMode: 1,
      openMode: 0,
    },
    defaultCommandTimeout: 8000,
    requestTimeout: 8000,
  },
})


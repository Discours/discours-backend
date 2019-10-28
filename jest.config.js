const { pathsToModuleNameMapper } = require("ts-jest/utils");
const { compilerOptions } = require("./tsconfig");

module.exports = {
  collectCoverageFrom: ["src/**/*.ts"],
  coverageReporters: ["json-summary", "text", "html"],
  errorOnDeprecated: true,
  globals: {
    "ts-jest": { isolatedModules: true }
  },

  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json"],
  moduleNameMapper: pathsToModuleNameMapper(compilerOptions.paths, {
    prefix: "<rootDir>/"
  }),
  preset: "ts-jest",
  setupFiles: [],
  setupFilesAfterEnv: ["jest-extended"],
  testMatch: ["**/__tests__/**/*.ts?(x)", "**/?(*.)+(spec).ts?(x)"]
};

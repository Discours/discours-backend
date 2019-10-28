class Env {
  get PUBLIC_URL(): string {
    return this.getVar("PUBLIC_URL", "http://localhost:4000/");
  }

  get POSTGRESQL_URL() {
    return this.getVar(
      "POSTGRESQL_URL",
      "postgresql://discours-backend@localhost:5432/discours-backend"
    );
  }

  get IS_PROD() {
    return process.env.NODE_ENV === "production";
  }

  get IS_DEV() {
    return process.env.NODE_ENV !== "production";
  }

  get ADMIN_API_KEY() {
    return this.getVar("ADMIN_API_KEY", "12345678");
  }

  private getVar(name: string, devValue?: string): string {
    if (!process.env[name] && this.IS_PROD) {
      throw new Error(`Please provide ${name} environment variable`);
    }
    if (!process.env[name] && this.IS_DEV && devValue) {
      return devValue;
    }
    return process.env[name] as string;
  }
}

export default new Env();

// Node 18+ provides global fetch in runtime, but TypeScript may need a lib.
// This declaration silences TS complaints for simple usage in the extension.
declare const fetch: (input: string, init?: any) => Promise<any>;


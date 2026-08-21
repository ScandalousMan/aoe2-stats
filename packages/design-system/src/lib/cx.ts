// Tiny class-name joiner. Not a token: it carries no style value of its own, only the plumbing to
// combine the ones components already pass it. Falsy entries (conditionals, `undefined`) drop out.
export type ClassValue = string | false | null | undefined

export function cx(...values: ClassValue[]): string {
  return values.filter(Boolean).join(' ')
}

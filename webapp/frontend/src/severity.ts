// Display names for the four severity states. The API value 'None' is shown as "No reaction".
export const severityName = (severity: string) => (severity === 'None' ? 'No reaction' : severity)

export const basisLabel = (basis: string | undefined, documented: boolean) => {
  if (basis === 'estimated') return 'Estimated'
  if (basis === 'no_record') return 'No record'
  if (basis === 'duplicate_class') return 'Same class'
  if (basis === 'inferred') return 'Inferred'
  if (basis === 'documented') return 'Documented'
  return documented ? 'Documented' : 'Inferred'
}

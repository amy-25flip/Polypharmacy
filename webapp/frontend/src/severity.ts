// Display names for the four severity states. The API value 'None' is shown as "No reaction".
// 'None' is an absence of a record, not a finding of safety, so the words say so.
export const severityName = (severity: string) => (severity === 'None' ? 'No interaction on record' : severity)

export const basisLabel = (basis: string | undefined, documented: boolean) => {
  if (basis === 'estimated') return 'Estimated'
  if (basis === 'no_record') return 'No record'
  if (basis === 'no_data') return 'Not checked'
  if (basis === 'class_rule') return 'Class warning'
  if (basis === 'duplicate_class') return 'Same class'
  if (basis === 'inferred') return 'Inferred'
  if (basis === 'documented') return 'Documented'
  return documented ? 'Documented' : 'Inferred'
}

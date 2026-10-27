export function isPatientInitializationAccepted<T extends {
  status: string;
  external_patient_id?: string;
}>(response: T): response is T & { external_patient_id: string } {
  return (
    (response.status === "success" || response.status === "exists") &&
    typeof response.external_patient_id === "string" &&
    response.external_patient_id.trim().length > 0
  );
}

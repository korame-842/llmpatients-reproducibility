import { eq } from "drizzle-orm";

import type { AppDb } from "~/server/db";
import { patients } from "~/server/db/tables";
import { parseStringArray } from "~/server/utils/json";
import type { InitializePatientInput } from "./patient-response-generator/types";
import {
  requireOwnedTherapySession,
  type OwnedTherapySession,
} from "./therapy-session-access";

export async function buildInitializePatientInput(
  dbClient: AppDb,
  therapySessionId: string,
  userId: string,
): Promise<{
  therapySession: OwnedTherapySession;
  initInput: InitializePatientInput;
}> {
  const therapySession = await requireOwnedTherapySession(dbClient, {
    therapySessionId,
    userId,
  });

  const patientResult = await dbClient
    .select({
      id: patients.id,
      externalPatientId: patients.externalPatientId,
      name: patients.name,
      age: patients.age,
      gender: patients.gender,
      diagnosis: patients.diagnosis,
      difficulty: patients.difficulty,
      psychologicalProfile: patients.psychologicalProfile,
      clinicalCase: patients.clinicalCase,
      currentMedications: patients.currentMedications,
      objectives: patients.objectives,
      previousSessions: patients.previousSessions,
    })
    .from(patients)
    .where(eq(patients.id, therapySession.patientId))
    .limit(1);

  const patient = patientResult[0];
  if (!patient) {
    throw new Error("Patient not found for therapy session");
  }

  return {
    therapySession,
    initInput: {
      sessionId: therapySession.id,
      patientInfo: {
        id: patient.externalPatientId?.trim() || patient.id,
        name: patient.name,
        age: patient.age,
        gender: patient.gender ?? "not specified",
        diagnosis: patient.diagnosis ?? "Not specified",
        difficulty: patient.difficulty,
        psychologicalProfile:
          patient.psychologicalProfile ?? patient.clinicalCase,
        background: patient.clinicalCase,
        currentMedications: parseStringArray(patient.currentMedications),
        therapyGoals: parseStringArray(patient.objectives),
        previousSessions: patient.previousSessions ?? 0,
      },
    },
  };
}

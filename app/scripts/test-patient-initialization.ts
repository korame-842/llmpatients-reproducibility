import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { parse as parseYaml } from "yaml";

import { isPatientInitializationAccepted } from "../src/lib/patient-initialization";
import type { AppDb } from "../src/server/db";
import { buildInitializePatientInput } from "../src/server/services/patient-initialization";

export async function testPatientInitializationBindings() {
  const directory = new URL("../patients/", import.meta.url);
  const files = readdirSync(directory).filter((name) => name.endsWith(".yaml"));
  assert.equal(files.length, 10);
  const externalIds = files.map((name) => {
    const source = parseYaml(readFileSync(new URL(name, directory), "utf8")) as {
      identifiers: { externalPatientId: string };
    };
    return source.identifiers.externalPatientId;
  });
  assert.ok(externalIds.includes("Jason_001"));

  for (const externalId of [...externalIds, null]) {
    const internalId = "00000000-0000-4000-8000-000000000001";
    const selections: string[][] = [];
    const rows = [
      [{ id: "session", patientId: internalId, externalPatientId: null }],
      [{ id: internalId, externalPatientId: externalId, name: "Offline profile",
        age: 30, gender: "other", diagnosis: null, difficulty: 1,
        psychologicalProfile: "Offline case", clinicalCase: "Offline case",
        currentMedications: null, objectives: null, previousSessions: 0 }],
    ];
    const fakeDb = {
      select(fields: Record<string, unknown>) {
        selections.push(Object.keys(fields));
        const result = rows.shift();
        return {
          from() { return this; },
          where() { return this; },
          async limit() { return result; },
        };
      },
    } as unknown as AppDb;
    const { initInput } = await buildInitializePatientInput(fakeDb, "session", "user");
    assert.ok(selections[1]?.includes("externalPatientId"));
    assert.equal(initInput.patientInfo.id, externalId ?? internalId);
    assert.equal(rows.length, 0);
  }

  assert.ok(isPatientInitializationAccepted({ status: "success", external_patient_id: "profile" }));
  assert.ok(isPatientInitializationAccepted({ status: "exists", external_patient_id: "profile" }));
  assert.ok(!isPatientInitializationAccepted({ status: "error", external_patient_id: "profile" }));
  assert.ok(!isPatientInitializationAccepted({ status: "exists" }));
  assert.ok(!isPatientInitializationAccepted({ status: "success", external_patient_id: " " }));
}

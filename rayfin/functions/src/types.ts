/**
 * Function schema types for RayfinClient.
 *
 * AUTO-GENERATED — do not edit manually.
 * Re-generated automatically when function source files change.
 *
 * If this file is not updating automatically, run:
 *   rayfin dev functions apply
 *
 * The schema is a closed object type: only the function names listed
 * below are accepted by RayfinClient.functions.<name>.invoke(...).
 * Adding, renaming, or changing the signature of a udf.func() call
 * regenerates this file and surfaces type errors at every consumer.
 *
 * IMPORTANT: This file must NOT import any Node.js packages — it is
 * resolved by the frontend app's TypeScript compiler.
 */

export type AppFunctionsSchema = {
  getTelemetry: {
    input: Record<string, never>;
    output: { checkedAt: string; devices: { [k: string]: null | string | number | false | true }[]; trend: { [k: string]: null | string | number | false | true }[]; invalidReadings: number };
  };
  getLoads: {
    input: Record<string, never>;
    output: { checkedAt: string; sources: { [k: string]: null | string | number | false | true }[]; tables: { [k: string]: null | string | number | false | true }[]; daily: { [k: string]: null | string | number | false | true }[]; duplicateKeys: number };
  };
  getFabricHealth: {
    input: Record<string, never>;
    output: { checkedAt: string; simulator: { id: string; status: string; startTimeUtc: string; endTimeUtc: null | string; failureReason?: undefined | null | { message?: undefined | string; errorCode?: undefined | string } }[]; pipeline: { id: string; status: string; startTimeUtc: string; endTimeUtc: null | string; failureReason?: undefined | null | { message?: undefined | string; errorCode?: undefined | string } }[]; schedules: { id: string; enabled: boolean; configuration: { endDateTime: string; localTimeZoneId: string; times?: undefined | string[] } }[]; eventstream: { name: string; sources: number; destinations: number } };
  };
};

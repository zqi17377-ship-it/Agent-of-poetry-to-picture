import type {Artwork, Job} from './api';

type Client = <T>(path: string) => Promise<T>;

// Publish terminal state together with its saved versions. A failed read leaves
// polling ownership intact so the whole snapshot can be retried safely.
export async function readJobSnapshot(jobId: string, client: Client): Promise<{job: Job; artwork?: Artwork}> {
  const job = await client<Job>('/jobs/' + jobId);
  if (['queued', 'running'].includes(job.status)) return {job};
  const artwork = await client<Artwork>('/artworks/' + job.artwork_id);
  return {job, artwork};
}

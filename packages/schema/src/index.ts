import { z } from "zod";

export const SourceCategorySchema = z.enum([
  "bahtsul_masail",
  "kitab_turats",
  "hadith",
  "quran_tafsir",
  "fatwa",
  "qawaid_fiqh",
]);

export type SourceCategory = z.infer<typeof SourceCategorySchema>;

export const VerificationStatusSchema = z.enum([
  "pending",
  "machine_verified",
  "scholarly_verified",
  "rejected",
]);

export type VerificationStatus = z.infer<typeof VerificationStatusSchema>;

export const LanguageSchema = z.enum(["ar", "id", "mixed"]);

export type Language = z.infer<typeof LanguageSchema>;

export const ContentSchema = z.object({
  arabic_raw: z.string(),
  arabic_clean: z.string(),
  indonesian: z.string().default(""),
  embedding_text: z.string().min(1),
});

export type ChunkContent = z.infer<typeof ContentSchema>;

export const CitationSchema = z.object({
  short_label: z.string().min(1),
  full_reference: z.string().min(1),
  url: z.string().url().optional().or(z.literal("")),
});

export type Citation = z.infer<typeof CitationSchema>;

export const ReferencedBookSchema = z.object({
  title: z.string().min(1),
  author: z.string().optional(),
  juz: z.number().int().positive().optional(),
  page: z.number().int().positive().optional(),
});

export type ReferencedBook = z.infer<typeof ReferencedBookSchema>;

export const MetadataSchema = z
  .object({
    forum: z.string().optional(),
    year: z.number().int().optional(),
    madzhab: z.string().optional(),
    verification_status: VerificationStatusSchema.default("pending"),
    footnotes: z.array(z.string()).default([]),
    referenced_books: z.array(ReferencedBookSchema).default([]),
  })
  .passthrough();

export type ChunkMetadata = z.infer<typeof MetadataSchema>;

export const JamiyyahChunkSchema = z.object({
  chunk_id: z.string().min(1),
  doc_id: z.string().min(1),
  source_category: SourceCategorySchema,
  language: LanguageSchema,
  hierarchy: z.array(z.string().min(1)).min(1),
  content: ContentSchema,
  citation: CitationSchema,
  metadata: MetadataSchema,
});

export type JamiyyahChunk = z.infer<typeof JamiyyahChunkSchema>;

export function validateChunk(input: unknown): JamiyyahChunk {
  return JamiyyahChunkSchema.parse(input);
}

export function validateJsonlLine(line: string): JamiyyahChunk {
  const parsed: unknown = JSON.parse(line);
  return validateChunk(parsed);
}

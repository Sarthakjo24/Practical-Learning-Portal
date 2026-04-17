export interface ModuleSummary {
  id: string;
  slug: string;
  title: string;
  description?: string | null;
  question_count: number;
}

export interface UserProfile {
  id: string;
  candidate_code: string;
  full_name: string;
  email: string;
  avatar_url?: string | null;
  last_login_at: string;
  is_admin: boolean;
  can_access_admin: boolean;
}

export interface CandidateQuestion {
  question_id: string;
  question_code: string;
  title: string;
  scenario_transcript: string;
  audio_url: string;
  display_order: number;
}

export interface StartSessionResponse {
  session_id: string;
  candidate_id: string;
  module_slug: string;
  module_title: string;
  status: string;
  questions: CandidateQuestion[];
}

export interface AnswerEvaluation {
  total_score: number;
  courtesy_score: number;
  respect_score: number;
  empathy_score: number;
  sympathy_score: number;
  tone_score: number;
  communication_clarity_score: number;
  engagement_score: number;
  problem_handling_approach_score: number;
  strengths: string[];
  improvement_areas: string[];
  final_summary: string;
  confidence_score?: number | null;
  created_at?: string | null;
}

export interface CandidateAnswerDetail {
  answer_id: string;
  question_id: string;
  question_code: string;
  question_title: string;
  display_order: number;
  status: string;
  question_audio_url: string;
  audio_url?: string | null;
  transcript_text?: string | null;
  standard_responses: string[];
  evaluation?: AnswerEvaluation | null;
}

export interface CandidateSessionDetail {
  session_id: string;
  candidate_id: string;
  status: string;
  module_slug: string;
  module_title: string;
  login_at: string;
  started_at?: string | null;
  submitted_at?: string | null;
  completed_at?: string | null;
  ai_score?: number | null;
  answers: CandidateAnswerDetail[];
}

export interface AdminCandidateListItem {
  session_id: string;
  candidate_id: string;
  name: string;
  email: string;
  module_title: string;
  status: string;
  ai_score?: number | null;
  evaluator_score?: number | null;
  submission_time?: string | null;
  login_time: string;
}

export interface AdminCandidateListResponse {
  page: number;
  page_size: number;
  total: number;
  items: AdminCandidateListItem[];
}

export interface ManualScore {
  id: string;
  admin_email: string;
  manual_score: number;
  notes?: string | null;
  created_at: string;
}

export interface AdminCandidateDetail {
  session_id: string;
  candidate_id: string;
  name: string;
  email: string;
  module_slug: string;
  module_title: string;
  status: string;
  ai_score?: number | null;
  overall_performance_summary?: string | null;
  latest_manual_score?: ManualScore | null;
  login_time: string;
  submission_time?: string | null;
  completed_at?: string | null;
  answers: CandidateAnswerDetail[];
}

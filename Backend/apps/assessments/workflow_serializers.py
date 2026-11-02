from rest_framework import serializers

from .models import AnswerSubmission, CriterionAssessment, QuestionEvaluation, TraineeAnswer
from .serializers import TraineeQuestionSerializer


class AnswerInputSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(min_value=1)
    answer_text = serializers.CharField(
        trim_whitespace=True,
        allow_blank=False,
        min_length=1,
        max_length=10000,
    )


class TraineeAnswerSerializer(serializers.ModelSerializer):
    question = TraineeQuestionSerializer(read_only=True)

    class Meta:
        model = TraineeAnswer
        fields = ['id', 'question', 'answer_text', 'created_at', 'updated_at']


class AnswerSubmissionSerializer(serializers.ModelSerializer):
    answers = TraineeAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = AnswerSubmission
        fields = [
            'id', 'status', 'submitted_at', 'evaluated_at', 'review_status',
            'overall_ai_score', 'overall_final_score', 'overall_ai_level',
            'overall_final_level', 'answers', 'created_at', 'updated_at',
        ]


class StaffQuestionEvaluationSerializer(serializers.ModelSerializer):
    question_id = serializers.IntegerField(source='answer.question_id', read_only=True)
    answer_text = serializers.CharField(source='answer.answer_text', read_only=True)
    criterion_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = QuestionEvaluation
        fields = [
            'question_id', 'answer_text', 'criterion_id', 'score', 'max_score', 'explanation',
            'evidence', 'strengths', 'missing_points', 'recommendations',
        ]


class TraineeQuestionEvaluationSerializer(StaffQuestionEvaluationSerializer):
    class Meta(StaffQuestionEvaluationSerializer.Meta):
        fields = [
            'question_id', 'answer_text', 'criterion_id', 'score', 'max_score', 'explanation',
            'evidence', 'strengths', 'missing_points', 'recommendations',
        ]


class CriterionAssessmentSerializer(serializers.ModelSerializer):
    criterion_name = serializers.CharField(source='criterion.name', read_only=True)
    score = serializers.DecimalField(source='effective_score', max_digits=8, decimal_places=2, read_only=True)
    level = serializers.CharField(source='effective_level', read_only=True)

    class Meta:
        model = CriterionAssessment
        fields = [
            'criterion_id', 'criterion_name', 'ai_score', 'score', 'max_score',
            'weight', 'ai_level', 'level', 'override_reason', 'overridden_by', 'overridden_at',
        ]


class AssessmentRunSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    submission_id = serializers.IntegerField(source='submission.id')
    trainee_id = serializers.IntegerField(source='submission.trainee_id')
    trainee_name = serializers.CharField(source='submission.trainee.get_full_name')
    task_id = serializers.IntegerField(source='submission.task_id')
    task_title = serializers.CharField(source='submission.task.title')
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

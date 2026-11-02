from rest_framework import serializers

from .models import GeneratedQuestion


class TraineeQuestionSerializer(serializers.ModelSerializer):
    competency_criterion = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedQuestion
        fields = [
            'id', 'question_text', 'competency_criterion', 'difficulty',
            'code_file', 'code_line', 'code_snippet', 'display_order', 'created_at',
        ]

    def get_competency_criterion(self, question):
        criterion = question.competency_criterion
        return {'id': criterion.id, 'name': criterion.name} if criterion else None


class StaffQuestionSerializer(TraineeQuestionSerializer):
    class Meta(TraineeQuestionSerializer.Meta):
        fields = TraineeQuestionSerializer.Meta.fields + ['expected_answer_points']

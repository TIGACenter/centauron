from django.shortcuts import render

# Create your views here.
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import FormView, TemplateView
from django.db import models

from apps.challenge.views import ChallengeContextMixin
from apps.challenge.website.forms import ProjectWebsiteForm
from apps.challenge.website.models import ChallengeWebsite


class CreateWebsiteView(LoginRequiredMixin, ChallengeContextMixin, FormView):
    template_name = 'challenge/website/create.html'
    form_class = ProjectWebsiteForm

    def _get_default_affiliation(self, profile):
        """Generate default affiliation from profile"""
        affiliation_parts = []
        if profile.organization:
            affiliation_parts.append(profile.organization)
        links = []
        if profile.orcid:
            links.append(f"[ORCID]({profile.orcid})")
        if profile.pubmed:
            links.append(f"[PubMed]({profile.pubmed})")
        if profile.google_scholar:
            links.append(f"[Google Scholar]({profile.google_scholar})")
        if links:
            affiliation_parts.append(" | ".join(links))
        if affiliation_parts:
            return "\n\n".join(affiliation_parts)
        return ""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # If a website already exists for this project, update it instead of creating a new one
        existing = ChallengeWebsite.objects.filter(challenge=self.get_challenge()).first()
        if existing is not None:
            kwargs['instance'] = existing
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        # Only set initial values if creating a new website (not editing existing)
        existing = ChallengeWebsite.objects.filter(challenge=self.get_challenge()).first()
        if existing is None:
            profile = getattr(self.request.user, 'profile', None)
            if profile:
                # Set default contact email
                initial['contact_email'] = getattr(self.request.user, 'email', None)
                # Set default affiliation from profile
                initial['affiliation'] = self._get_default_affiliation(profile)
        return initial

    def form_valid(self, form):
        obj = form.save(commit=False)
        # Always ensure the object is linked to the current project
        obj.challenge = self.get_challenge()
        # Only set created_by upon creation
        if obj.created_by_id is None:
            profile = getattr(self.request.user, 'profile', None)
            if profile is None:
                raise Http404('Profile not found for user')
            obj.created_by = profile
        obj.save()
        return redirect('challenge:website:create', pk=self.get_challenge_id())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        website = ChallengeWebsite.objects.filter(challenge=self.get_challenge()).first()
        ctx['website'] = website

        # Add default values to context for reset functionality
        profile = getattr(self.request.user, 'profile', None)
        if profile:
            ctx['default_contact_email'] = getattr(self.request.user, 'email', '') or ''
            ctx['default_affiliation'] = self._get_default_affiliation(profile)
        else:
            ctx['default_contact_email'] = ''
            ctx['default_affiliation'] = ''

        return ctx

class PreviewView(LoginRequiredMixin, ChallengeContextMixin, TemplateView):
    template_name = 'challenge/website/preview.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        objects_filter = ChallengeWebsite.objects.filter(pk=kwargs['website_pk'])
        if not objects_filter.exists():
            raise Http404()

        website = objects_filter.first()
        project = self.get_challenge().project
        # contributors are accepted members including origin
        contributors = project.get_project_members().select_related('user')

        # Add statistics for each contributor
        contributors_with_stats = []
        for member in contributors:
            # Count files contributed by this user
            user_files = project.files.filter(origin=member.user).distinct()
            file_count = user_files.count()
            # Count unique cases from those files
            case_count = user_files.values('case').distinct().count()

            contributors_with_stats.append({
                'member': member,
                'file_count': file_count,
                'case_count': case_count,
                'orcid': member.user.orcid,
                'pubmed': member.user.pubmed,
                'google_scholar': member.user.google_scholar,
            })

        # compute overall statistics
        files_qs = project.files.all().distinct()
        cases_qs = getattr(project, 'cases', None)
        total_file_count = files_qs.count()
        # Only sum size of imported files with size >=0
        total_size = files_qs.filter(size__gte=0).aggregate(models.Sum('size'))['size__sum'] or 0
        total_case_count = cases_qs.count() if cases_qs is not None else 0

        def code_list(qs):
            return [c.get_readable_str() if hasattr(c, 'get_readable_str') else getattr(c, 'code', str(c)) for c in qs.all()]

        ctx.update({
            'website': website,
            'slogan': website.slogan,
            'population': project.population,
            'intended_use': project.intended_use,
            'biomarkers': code_list(project.biomarkers),
            'tissue': code_list(project.tissue),
            'disease': code_list(project.disease),
            'contributors': contributors_with_stats,
            'stats': {
                'file_count': total_file_count,
                'case_count': total_case_count,
                'total_size': total_size,
            }
        })
        return ctx

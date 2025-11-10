# Create your views here.
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import FormView, TemplateView
from django.db import models
import yaml

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
        challenge = self.get_challenge()
        project = challenge.project

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

            # Get initials from name
            name = member.user.human_readable #get_full_name() or member.user.email.split('@')[0]
            name_parts = name.split()
            initials = ''.join([part[0].upper() for part in name_parts if part]) if name_parts else 'U'

            contributors_with_stats.append({
                'member': member,
                'name': name,
                'initials': initials,
                'file_count': file_count,
                'case_count': case_count,
                'orcid': member.user.orcid,
                'pubmed': member.user.pubmed,
                'google_scholar': member.user.google_scholar,
                'organization': member.user.organization or '',
                'email': member.user.email if hasattr(member.user, 'email') else '',
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

        # Get biomarkers, tissue, and disease information
        biomarkers = code_list(project.biomarkers)
        tissue = code_list(project.tissue)
        disease = code_list(project.disease)

        # Determine the principal investigator (challenge creator)
        pi = challenge.created_by
        pi_name = pi.human_readable if pi and hasattr(pi, 'human_readable') else 'Principal Investigator'
        pi_parts = pi_name.split()
        pi_initials = ''.join([part[0].upper() for part in pi_parts if part]) if pi_parts else 'PI'

        # Get number of clinical sites (number of contributors)
        num_sites = contributors.count()

        # Get target metrics for evaluation
        target_metrics = challenge.target_metrics.all().order_by('sort', 'key')
        evaluation_metrics = []
        for metric in target_metrics:
            evaluation_metrics.append({
                'key': metric.key,
                'sort': metric.sort,
                'dtype': metric.dtype,
                'filename': metric.filename,
                'name': metric.name,
                'description': metric.description,
            })

        # Get clinical endpoints from ground truth schema
        clinical_endpoints = []
        ground_truth_schema = project.latest_ground_truth_schema
        if ground_truth_schema and ground_truth_schema.yaml:
            try:
                schema_data = yaml.safe_load(ground_truth_schema.yaml)
                if isinstance(schema_data, dict) and 'columns' in schema_data:
                    for column in schema_data['columns']:
                        if isinstance(column, dict) and column.get('is_endpoint', False):
                            clinical_endpoints.append({
                                'name': column.get('name', ''),
                                'description': column.get('description', ''),
                            })
            except yaml.YAMLError:
                # If YAML parsing fails, just use empty list
                pass

        # Challenge context data
        challenge_data = {
            'title': challenge.name,
            'description': challenge.description or website.slogan or 'Advance medical AI by developing models on real-world clinical data.',
            'dataset_size': f"{total_case_count}+" if total_case_count > 0 else "N/A",
            'num_sites': f"{num_sites}+" if num_sites > 0 else "1+",
            'data_modalities': f"{total_file_count}+" if total_file_count > 0 else "Multiple",
            'num_participants': "Open",  # Could be enhanced with actual participant count
            'contact_email': website.contact_email or (self.request.user.email if hasattr(self.request.user, 'email') else 'info@centauron.net'),
            'year': challenge.date_created.year if challenge.date_created else 2025,
            'organization': pi.organization if pi and hasattr(pi, 'organization') else 'Centauron Network',

            # Clinical context
            'population_size': f"{total_case_count} cases" if total_case_count > 0 else "N cases",
            'population': project.population or "Diverse clinical cohort",
            'intended_use': project.intended_use or "Clinical prediction and decision support",

            # Biomarkers, tissue, disease
            'molecular_markers': ', '.join(biomarkers[:3]) if biomarkers else "Gene expression, mutations",
            'tissue_type': ', '.join(tissue[:3]) if tissue else "Multiple tissue types",
            'disease_type': ', '.join(disease[:3]) if disease else "Clinical condition",
            'biomarkers_list': biomarkers,
            'tissue_list': tissue,
            'disease_list': disease,

            # Principal Investigator
            'pi_name': pi_name,
            'pi_initials': pi_initials,
            'pi_title': 'Principal Investigator',
            'pi_affiliation': website.affiliation or (pi.organization if pi and hasattr(pi, 'organization') else 'Research Institution'),
            'pi_bio': f"Leading the {challenge.name} initiative.",
            'pi_email': website.contact_email or (pi.email if pi and hasattr(pi, 'email') else None),

            # Challenge dates
            'open_from': challenge.open_from,
            'open_until': challenge.open_until,

            # Citation
            'citation': f"{pi_name} et al. ({challenge.date_created.year if challenge.date_created else 2025}). {challenge.name}. Centauron Platform. https://hub.centauron.io/",
            'authors': pi_name,
            'url': self.request.build_absolute_uri(challenge.get_absolute_url()) if hasattr(challenge, 'get_absolute_url') else "https://hub.centauron.io/",

            # Evaluation Metrics
            'evaluation_metrics': evaluation_metrics,

            # Clinical Endpoints from Ground Truth Schema
            'clinical_endpoints': clinical_endpoints,
        }

        ctx.update({
            'website': website,
            'challenge': challenge_data,
            'slogan': website.slogan,
            'population': project.population,
            'intended_use': project.intended_use,
            'biomarkers': biomarkers,
            'tissue': tissue,
            'disease': disease,
            'contributors': contributors_with_stats,
            'stats': {
                'file_count': total_file_count,
                'case_count': total_case_count,
                'total_size': total_size,
            }
        })
        return ctx

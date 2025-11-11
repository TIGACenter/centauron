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
        # Pass challenge to form so it can load available endpoints
        kwargs['challenge'] = self.get_challenge()
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

        # Generate detailed dataset statistics per dataset (public vs hidden)
        dataset_statistics = self._generate_dataset_statistics(challenge)

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
        if ground_truth_schema:
            # Get selected endpoints from website configuration
            selected_endpoint_names = website.selected_endpoints if website.selected_endpoints else []

            # Use the model's get_endpoints method
            all_endpoints = ground_truth_schema.get_endpoints()

            # Filter based on selected endpoints
            for endpoint in all_endpoints:
                endpoint_name = endpoint['name']
                # Only include endpoint if it's in the selected list (or if no selection was made, include all)
                if not selected_endpoint_names or endpoint_name in selected_endpoint_names:
                    clinical_endpoints.append({
                        'name': endpoint_name,
                        'description': endpoint['description'],
                    })

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
            'citation': None if not website.citation or len(website.citation.strip()) == 0 else website.citation,
            'bibtex': None if not website.bibtex or len(website.bibtex.strip()) == 0 else website.bibtex,
            'authors': pi_name,
            'url': self.request.build_absolute_uri(challenge.get_absolute_url()) if hasattr(challenge, 'get_absolute_url') else "https://hub.centauron.io/",

            # Evaluation Metrics
            'evaluation_metrics': evaluation_metrics,

            # Clinical Endpoints from Ground Truth Schema
            'clinical_endpoints': clinical_endpoints,

            # Dataset Statistics
            'dataset_statistics': dataset_statistics,
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

    def _generate_dataset_statistics(self, challenge):
        """
        Generate comprehensive dataset statistics for both public and hidden datasets.
        Public dataset: is_public=True
        Hidden dataset: is_public=False and type='validation'
        """
        from apps.challenge.challenge_dataset.models import Dataset

        statistics = {
            'public': None,
            'hidden': None,
        }

        # Get public dataset (is_public=True)
        public_dataset = challenge.datasets.filter(is_public=True).first()
        if public_dataset:
            statistics['public'] = self._generate_single_dataset_statistics(public_dataset)

        # Get hidden/validation dataset (is_public=False, type='validation')
        hidden_dataset = challenge.datasets.filter(is_public=False, type=Dataset.Type.VALIDATION).first()
        if hidden_dataset:
            statistics['hidden'] = self._generate_single_dataset_statistics(hidden_dataset)

        return statistics

    def _generate_single_dataset_statistics(self, dataset):
        """
        Generate statistics for a single dataset.
        """
        from collections import Counter
        from apps.terminology.models import Code

        files_qs = dataset.files.all()
        cases_qs = dataset.cases.all()

        stats = {
            'name': dataset.name,
            'type': dataset.type,
            'is_public': dataset.is_public,
            'file_types': [],
            'terminology': {
                'disease': [],
                'tissue': [],
                'biomarkers': [],
            },
            'all_terms': [],
            'case_statistics': {
                'total_cases': 0,
                'cases_per_contributor': [],
                'files_per_case': {
                    'min': 0,
                    'max': 0,
                    'avg': 0,
                    'distribution': []
                }
            },
            'overview': {
                'total_files': files_qs.count(),
                'total_cases': cases_qs.count(),
                'total_size_gb': 0,
            }
        }

        # Calculate total size in GB
        total_size_bytes = files_qs.filter(size__gte=0).aggregate(models.Sum('size'))['size__sum'] or 0
        stats['overview']['total_size_gb'] = round(total_size_bytes / (1024**3), 2) if total_size_bytes > 0 else 0

        # File type statistics - using content_type field
        file_type_counter = Counter()
        for file in files_qs.only('content_type', 'name'):
            if file.content_type:
                file_type_counter[file.content_type] += 1
            else:
                # Get file extension from filename as fallback
                if file.name:
                    ext = file.name.split('.')[-1].upper() if '.' in file.name else 'Unknown'
                    file_type_counter[ext] += 1
                else:
                    file_type_counter['Unknown'] += 1

        # Sort by count (descending)
        for file_type, count in file_type_counter.most_common():
            percentage = round((count / stats['overview']['total_files'] * 100), 1) if stats['overview']['total_files'] > 0 else 0
            stats['file_types'].append({
                'name': file_type,
                'count': count,
                'percentage': percentage
            })

        # Get terminology from cases (disease, tissue, biomarkers from project level)
        if cases_qs.count() > 0:
            project = dataset.challenge.project

            # Get disease codes from project-level disease field
            disease_codes = project.disease.all()
            tissue_codes = project.tissue.all()
            biomarker_codes = project.biomarkers.all()

            # Count how many cases have each disease code
            disease_counter = Counter()
            for disease_code in disease_codes:
                count = cases_qs.filter(codes=disease_code).count()
                if count > 0:
                    disease_name = disease_code.get_readable_str() if hasattr(disease_code, 'get_readable_str') else getattr(disease_code, 'code', str(disease_code))
                    disease_counter[disease_name] = count

            for disease_name, count in disease_counter.most_common():
                percentage = round((count / stats['overview']['total_cases'] * 100), 1) if stats['overview']['total_cases'] > 0 else 0
                stats['terminology']['disease'].append({
                    'name': disease_name,
                    'file_count': count,
                    'percentage': percentage
                })

            # Count how many cases have each tissue code
            tissue_counter = Counter()
            for tissue_code in tissue_codes:
                count = cases_qs.filter(codes=tissue_code).count()
                if count > 0:
                    tissue_name = tissue_code.get_readable_str() if hasattr(tissue_code, 'get_readable_str') else getattr(tissue_code, 'code', str(tissue_code))
                    tissue_counter[tissue_name] = count

            for tissue_name, count in tissue_counter.most_common():
                percentage = round((count / stats['overview']['total_cases'] * 100), 1) if stats['overview']['total_cases'] > 0 else 0
                stats['terminology']['tissue'].append({
                    'name': tissue_name,
                    'file_count': count,
                    'percentage': percentage
                })

            # Count how many cases have each biomarker code
            biomarker_counter = Counter()
            for biomarker_code in biomarker_codes:
                count = cases_qs.filter(codes=biomarker_code).count()
                if count > 0:
                    biomarker_name = biomarker_code.get_readable_str() if hasattr(biomarker_code, 'get_readable_str') else getattr(biomarker_code, 'code', str(biomarker_code))
                    biomarker_counter[biomarker_name] = count

            for biomarker_name, count in biomarker_counter.most_common():
                percentage = round((count / stats['overview']['total_cases'] * 100), 1) if stats['overview']['total_cases'] > 0 else 0
                stats['terminology']['biomarkers'].append({
                    'name': biomarker_name,
                    'file_count': count,
                    'percentage': percentage
                })

            # Get ALL terms in the dataset (from both cases and files)
            term_counter = Counter()

            # Get terms from cases
            case_code_ids = cases_qs.values_list('codes', flat=True).distinct()
            case_codes = Code.objects.filter(id__in=case_code_ids)
            for code in case_codes:
                code_name = code.get_readable_str() if hasattr(code, 'get_readable_str') else getattr(code, 'code', str(code))
                count = cases_qs.filter(codes=code).count()
                term_counter[code_name] += count

            # Get terms from files
            file_code_ids = files_qs.values_list('codes', flat=True).distinct()
            file_codes = Code.objects.filter(id__in=file_code_ids)
            for code in file_codes:
                code_name = code.get_readable_str() if hasattr(code, 'get_readable_str') else getattr(code, 'code', str(code))
                count = files_qs.filter(codes=code).count()
                term_counter[code_name] += count

            # Sort by count and add to statistics
            for term_name, count in term_counter.most_common():
                stats['all_terms'].append({
                    'name': term_name,
                    'count': count,
                })

            # Calculate case statistics
            stats['case_statistics']['total_cases'] = cases_qs.count()

            # Files per case distribution
            from django.db.models import Count
            cases_with_file_counts = cases_qs.annotate(file_count=Count('files')).values_list('file_count', flat=True)
            file_counts_list = list(cases_with_file_counts)

            if file_counts_list:
                stats['case_statistics']['files_per_case']['min'] = min(file_counts_list)
                stats['case_statistics']['files_per_case']['max'] = max(file_counts_list)
                stats['case_statistics']['files_per_case']['avg'] = round(sum(file_counts_list) / len(file_counts_list), 1)

                # Create distribution buckets
                file_count_counter = Counter(file_counts_list)
                for file_count, case_count in sorted(file_count_counter.items()):
                    percentage = round((case_count / stats['case_statistics']['total_cases'] * 100), 1)
                    stats['case_statistics']['files_per_case']['distribution'].append({
                        'file_count': file_count,
                        'case_count': case_count,
                        'percentage': percentage
                    })

            # Cases per contributor
            contributor_case_counts = cases_qs.values('origin').annotate(case_count=Count('id')).order_by('-case_count')
            for contrib in contributor_case_counts[:10]:  # Top 10 contributors
                origin_id = contrib['origin']
                case_count = contrib['case_count']
                percentage = round((case_count / stats['case_statistics']['total_cases'] * 100), 1)

                # Get contributor name
                from apps.user.user_profile.models import Profile
                try:
                    contributor = Profile.objects.get(id=origin_id)
                    contributor_name = contributor.human_readable if hasattr(contributor, 'human_readable') else 'Unknown'
                except Profile.DoesNotExist:
                    contributor_name = 'Unknown'

                stats['case_statistics']['cases_per_contributor'].append({
                    'contributor': contributor_name,
                    'case_count': case_count,
                    'percentage': percentage
                })

        return stats


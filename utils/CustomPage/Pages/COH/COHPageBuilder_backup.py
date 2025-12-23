"""
Cost Optimization Hub Page Builder

This module generates HTML pages for the Cost Optimization Hub custom page.
It follows the existing CustomPageBuilder pattern used by other Service Screener
custom pages while providing specialized cost optimization visualizations.
"""

import json
import uuid
from datetime import datetime
from utils.CustomPage.CustomPageBuilder import CustomPageBuilder
from utils.Config import Config
import constants as _C


class COHPageBuilder(CustomPageBuilder):
    """
    Page builder for Cost Optimization Hub
    
    Inherits from CustomPageBuilder to integrate with Service Screener's page generation
    infrastructure while providing specialized cost optimization HTML generation.
    """
    
    def __init__(self, service='coh', reporter=None):
        super().__init__(service, reporter)
        self.hasError = False
        self.error_message = ""
    
    def customPageInit(self):
        """Initialize custom page with error checking"""
        if hasattr(self.data, 'error_messages') and self.data.error_messages:
            self.hasError = True
            self.error_message = "; ".join(self.data.error_messages)
        
        # Check if we have any recommendations
        if not hasattr(self.data, 'recommendations') or not self.data.recommendations:
            if not self.hasError:
                self.hasError = True
                self.error_message = "No cost optimization recommendations found. This may be due to insufficient permissions, service not enabled, or no optimization opportunities available."
        
        return
    
    def buildContentSummary_customPage(self):
        """Build summary content for the COH page"""
        if self.hasError:
            return [f"<span class='text-danger'>{self.error_message}</span>"]
        
        if not self.data.executive_summary:
            return ["<span>No executive summary available</span>"]
        
        summary = self.data.executive_summary
        
        # Create executive summary cards
        summary_cards = []
        
        # Total savings card
        total_monthly = f"${summary.total_monthly_savings:,.2f}"
        total_annual = f"${summary.total_annual_savings:,.2f}"
        savings_card = f"""
        <div class="col-md-3">
            <div class="info-box bg-success">
                <span class="info-box-icon"><i class="fas fa-dollar-sign"></i></span>
                <div class="info-box-content">
                    <span class="info-box-text">Potential Savings</span>
                    <span class="info-box-number">{total_monthly}/month</span>
                    <span class="info-box-more">{total_annual}/year</span>
                </div>
            </div>
        </div>
        """
        
        # Total recommendations card
        recommendations_card = f"""
        <div class="col-md-3">
            <div class="info-box bg-info">
                <span class="info-box-icon"><i class="fas fa-lightbulb"></i></span>
                <div class="info-box-content">
                    <span class="info-box-text">Recommendations</span>
                    <span class="info-box-number">{summary.total_recommendations}</span>
                    <span class="info-box-more">optimization opportunities</span>
                </div>
            </div>
        </div>
        """
        
        # High priority recommendations card
        high_priority_card = f"""
        <div class="col-md-3">
            <div class="info-box bg-warning">
                <span class="info-box-icon"><i class="fas fa-exclamation-triangle"></i></span>
                <div class="info-box-content">
                    <span class="info-box-text">High Priority</span>
                    <span class="info-box-number">{summary.high_priority_count}</span>
                    <span class="info-box-more">immediate actions</span>
                </div>
            </div>
        </div>
        """
        
        # Data freshness card
        freshness = summary.data_freshness.strftime('%Y-%m-%d %H:%M UTC')
        freshness_card = f"""
        <div class="col-md-3">
            <div class="info-box bg-secondary">
                <span class="info-box-icon"><i class="fas fa-clock"></i></span>
                <div class="info-box-content">
                    <span class="info-box-text">Last Updated</span>
                    <span class="info-box-number" style="font-size: 14px;">{freshness}</span>
                    <span class="info-box-more">data freshness</span>
                </div>
            </div>
        </div>
        """
        
        summary_html = f"""
        <div class="row">
            {savings_card}
            {recommendations_card}
            {high_priority_card}
            {freshness_card}
        </div>
        """
        
        return [summary_html]
    
    def buildContentDetail_customPage(self):
        """Build detailed content for the COH page"""
        if self.hasError:
            return []
        
        output = []
        
        # Build recommendations by priority
        priority_sections = self._build_priority_sections()
        output.extend(priority_sections)
        
        # Build recommendations by category
        category_sections = self._build_category_sections()
        output.extend(category_sections)
        
        # Build top savings opportunities
        top_savings_section = self._build_top_savings_section()
        output.append(top_savings_section)
        
        return output
    
    def _build_priority_sections(self):
        """Build sections organized by priority level"""
        output = []
        
        recommendations_by_priority = self.data.get_recommendations_by_priority()
        
        priority_config = {
            'high': {'badge': 'danger', 'icon': 'fas fa-exclamation-triangle', 'title': 'High Priority Recommendations'},
            'medium': {'badge': 'warning', 'icon': 'fas fa-exclamation-circle', 'title': 'Medium Priority Recommendations'},
            'low': {'badge': 'info', 'icon': 'fas fa-info-circle', 'title': 'Low Priority Recommendations'}
        }
        
        for priority in ['high', 'medium', 'low']:
            recommendations = recommendations_by_priority.get(priority, [])
            if not recommendations:
                continue
            
            config = priority_config[priority]
            
            # Create table for this priority level
            thead = [
                "Service", "Recommendation", "Monthly Savings", "Annual Savings", 
                "Implementation Effort", "Affected Resources", "Actions"
            ]
            
            rows = []
            for rec in recommendations:
                row = [
                    rec.service.upper(),
                    f"<strong>{rec.title}</strong><br><small class='text-muted'>{rec.description[:100]}...</small>",
                    f"${rec.monthly_savings:,.2f}",
                    f"${rec.annual_savings:,.2f}",
                    f"<span class='badge badge-{self._get_effort_badge_class(rec.implementation_effort)}'>{rec.implementation_effort.title()}</span>",
                    str(rec.resource_count),
                    f"<button class='btn btn-sm btn-outline-primary' onclick='showRecommendationDetails(\"{rec.id}\")'>View Details</button>"
                ]
                
                # Add description as expandable content
                row.append(rec.description)
                rows.append(row)
            
            table_html = self._format_recommendations_table(thead, rows)
            
            card_title = f"<i class='{config['icon']}'></i> {config['title']} <span class='badge badge-{config['badge']}'>{len(recommendations)}</span>"
            
            card = self.generateCard(
                pid=self.getHtmlId(f"priority_{priority}"),
                html=table_html,
                cardClass='primary',
                title=card_title,
                titleBadge='',
                collapse=True,
                noPadding=False
            )
            
            items = [[card, '']]
            output.append(self.generateRowWithCol(12, items, "data-context='priorityTable'"))
        
        return output
    
    def _build_category_sections(self):
        """Build sections organized by service category"""
        output = []
        
        recommendations_by_category = self.data.get_recommendations_by_category()
        
        category_config = {
            'compute': {'icon': 'fas fa-server', 'title': 'Compute Optimization'},
            'storage': {'icon': 'fas fa-hdd', 'title': 'Storage Optimization'},
            'database': {'icon': 'fas fa-database', 'title': 'Database Optimization'},
            'commitment': {'icon': 'fas fa-handshake', 'title': 'Commitment Discounts'},
            'general': {'icon': 'fas fa-cogs', 'title': 'General Optimization'}
        }
        
        for category, recommendations in recommendations_by_category.items():
            if not recommendations:
                continue
            
            config = category_config.get(category, {'icon': 'fas fa-cogs', 'title': category.title()})
            
            # Calculate category totals
            total_monthly = sum(rec.monthly_savings for rec in recommendations)
            total_annual = sum(rec.annual_savings for rec in recommendations)
            
            # Create table for this category
            thead = [
                "Priority", "Recommendation", "Monthly Savings", "Annual Savings", 
                "Implementation Effort", "Source", "Actions"
            ]
            
            rows = []
            for rec in recommendations:
                priority_badge = f"<span class='badge badge-{self._get_priority_badge_class(rec.priority_level)}'>{rec.priority_level.title()}</span>"
                
                row = [
                    priority_badge,
                    f"<strong>{rec.title}</strong><br><small class='text-muted'>{rec.description[:100]}...</small>",
                    f"${rec.monthly_savings:,.2f}",
                    f"${rec.annual_savings:,.2f}",
                    f"<span class='badge badge-{self._get_effort_badge_class(rec.implementation_effort)}'>{rec.implementation_effort.title()}</span>",
                    rec.source.replace('_', ' ').title(),
                    f"<button class='btn btn-sm btn-outline-primary' onclick='showRecommendationDetails(\"{rec.id}\")'>View Details</button>"
                ]
                
                # Add description as expandable content
                row.append(rec.description)
                rows.append(row)
            
            table_html = self._format_recommendations_table(thead, rows)
            
            card_title = f"<i class='{config['icon']}'></i> {config['title']} <span class='badge badge-success'>${total_monthly:,.2f}/month</span>"
            
            card = self.generateCard(
                pid=self.getHtmlId(f"category_{category}"),
                html=table_html,
                cardClass='info',
                title=card_title,
                titleBadge='',
                collapse=True,
                noPadding=False
            )
            
            items = [[card, '']]
            output.append(self.generateRowWithCol(12, items, "data-context='categoryTable'"))
        
        return output
    
    def _build_top_savings_section(self):
        """Build section showing top savings opportunities"""
        if not self.data.executive_summary or not self.data.executive_summary.top_categories:
            return ""
        
        top_categories = self.data.executive_summary.top_categories
        
        # Create chart data for top categories
        chart_data = {
            'labels': [cat['category'].title() for cat in top_categories],
            'data': [cat['savings'] for cat in top_categories]
        }
        
        chart_html = f"""
        <div class="row">
            <div class="col-md-8">
                <canvas id="topCategoriesChart" width="400" height="200"></canvas>
            </div>
            <div class="col-md-4">
                <h5>Top Savings Categories</h5>
                <ul class="list-group">
        """
        
        for cat in top_categories:
            chart_html += f"""
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        {cat['category'].title()}
                        <span class="badge badge-success badge-pill">${cat['savings']:,.2f}/month</span>
                    </li>
            """
        
        chart_html += """
                </ul>
            </div>
        </div>
        
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            var ctx = document.getElementById('topCategoriesChart').getContext('2d');
            var chart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: """ + json.dumps(chart_data['labels']) + """,
                    datasets: [{
                        data: """ + json.dumps(chart_data['data']) + """,
                        backgroundColor: [
                            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        },
                        title: {
                            display: true,
                            text: 'Savings Potential by Category'
                        }
                    }
                }
            });
        });
        </script>
        """
        
        card = self.generateCard(
            pid=self.getHtmlId("top_savings"),
            html=chart_html,
            cardClass='success',
            title="<i class='fas fa-chart-pie'></i> Top Savings Opportunities",
            titleBadge='',
            collapse=False,
            noPadding=False
        )
        
        items = [[card, '']]
        return self.generateRowWithCol(12, items, "data-context='topSavings'")
    
    def _format_recommendations_table(self, thead, rows):
        """Format recommendations as an expandable table"""
        html = ["<table class='table table-bordered table-hover table-striped'>"]
        
        # Table header
        html.append("<thead class='thead-light'><tr>")
        for header in thead:
            html.append(f"<th>{header}</th>")
        html.append("</tr></thead>")
        
        # Table body
        html.append("<tbody>")
        for row in rows:
            html.append("<tr data-widget='expandable-table' aria-expanded='false'>")
            
            # Display columns (all except the last one which is description)
            for i in range(len(thead)):
                html.append(f"<td>{row[i]}</td>")
            
            html.append("</tr>")
            
            # Expandable row with full description
            if len(row) > len(thead):
                html.append(f"<tr class='expandable-body d-none'><td colspan='{len(thead)}'><div class='p-3'><h6>Description:</h6><p>{row[-1]}</p></div></td></tr>")
        
        html.append("</tbody></table>")
        
        return ''.join(html)
    
    def _get_priority_badge_class(self, priority):
        """Get Bootstrap badge class for priority level"""
        return {
            'high': 'danger',
            'medium': 'warning', 
            'low': 'info'
        }.get(priority, 'secondary')
    
    def _get_effort_badge_class(self, effort):
        """Get Bootstrap badge class for implementation effort"""
        return {
            'low': 'success',
            'medium': 'warning',
            'high': 'danger'
        }.get(effort, 'secondary')
    
    def embed_cost_data(self, html_content):
        """Embed cost optimization data into HTML for React components"""
        if not hasattr(self.data, 'to_dict'):
            return html_content
        
        cost_data = self.data.to_dict()
        
        # Embed data as JSON in script tag
        data_script = f"""
        <script type="text/javascript">
            window.__COH_DATA__ = {json.dumps(cost_data, default=str)};
        </script>
        """
        
        # Insert before closing body tag
        if '</body>' in html_content:
            html_content = html_content.replace('</body>', f'{data_script}</body>')
        else:
            html_content += data_script
        
        return html_content
    
    def build_responsive_dashboard_layout(self):
        """Build responsive dashboard layout with executive summary and key metrics"""
        if self.hasError:
            return self._build_error_dashboard()
        
        dashboard_sections = []
        
        # Executive Summary Section
        executive_section = self._build_executive_dashboard_section()
        dashboard_sections.append(executive_section)
        
        # Key Metrics Section
        metrics_section = self._build_key_metrics_section()
        dashboard_sections.append(metrics_section)
        
        # Quick Actions Section
        quick_actions_section = self._build_quick_actions_section()
        dashboard_sections.append(quick_actions_section)
        
        # Implementation Roadmap Section
        roadmap_section = self._build_implementation_roadmap_section()
        dashboard_sections.append(roadmap_section)
        
        return dashboard_sections
    
    def _build_error_dashboard(self):
        """Build error dashboard when there are issues"""
        error_html = f"""
        <div class="alert alert-danger" role="alert">
            <h4 class="alert-heading"><i class="fas fa-exclamation-triangle"></i> Cost Optimization Hub Error</h4>
            <p>{self.error_message}</p>
            <hr>
            <p class="mb-0">
                <strong>Possible solutions:</strong>
                <ul>
                    <li>Ensure Cost Optimization Hub is enabled in your AWS account</li>
                    <li>Verify IAM permissions for cost optimization services</li>
                    <li>Check if you have cost optimization recommendations available</li>
                    <li>Try refreshing the data or running the scan again</li>
                </ul>
            </p>
        </div>
        """
        
        card = self.generateCard(
            pid=self.getHtmlId("error_dashboard"),
            html=error_html,
            cardClass='danger',
            title="<i class='fas fa-exclamation-triangle'></i> Error",
            titleBadge='',
            collapse=False,
            noPadding=False
        )
        
        items = [[card, '']]
        return [self.generateRowWithCol(12, items)]
    
    def _build_executive_dashboard_section(self):
        """Build executive dashboard section with high-level metrics"""
        if not hasattr(self.data, 'executive_summary') or not self.data.executive_summary:
            return ""
        
        summary = self.data.executive_summary
        
        # Executive summary cards with enhanced styling
        executive_html = f"""
        <div class="row">
            <div class="col-lg-3 col-md-6">
                <div class="small-box bg-success">
                    <div class="inner">
                        <h3>${summary.total_monthly_savings:,.0f}</h3>
                        <p>Monthly Savings Potential</p>
                    </div>
                    <div class="icon">
                        <i class="fas fa-dollar-sign"></i>
                    </div>
                    <div class="small-box-footer">
                        ${summary.total_annual_savings:,.0f}/year <i class="fas fa-arrow-circle-right"></i>
                    </div>
                </div>
            </div>
            
            <div class="col-lg-3 col-md-6">
                <div class="small-box bg-info">
                    <div class="inner">
                        <h3>{summary.total_recommendations}</h3>
                        <p>Optimization Opportunities</p>
                    </div>
                    <div class="icon">
                        <i class="fas fa-lightbulb"></i>
                    </div>
                    <div class="small-box-footer">
                        {summary.high_priority_count} high priority <i class="fas fa-arrow-circle-right"></i>
                    </div>
                </div>
            </div>
            
            <div class="col-lg-3 col-md-6">
                <div class="small-box bg-warning">
                    <div class="inner">
                        <h3>{summary.high_priority_count}</h3>
                        <p>Immediate Actions</p>
                    </div>
                    <div class="icon">
                        <i class="fas fa-exclamation-triangle"></i>
                    </div>
                    <div class="small-box-footer">
                        Requires attention <i class="fas fa-arrow-circle-right"></i>
                    </div>
                </div>
            </div>
            
            <div class="col-lg-3 col-md-6">
                <div class="small-box bg-secondary">
                    <div class="inner">
                        <h3 style="font-size: 1.5rem;">{summary.data_freshness.strftime('%m/%d')}</h3>
                        <p>Last Updated</p>
                    </div>
                    <div class="icon">
                        <i class="fas fa-clock"></i>
                    </div>
                    <div class="small-box-footer">
                        {summary.data_freshness.strftime('%H:%M UTC')} <i class="fas fa-arrow-circle-right"></i>
                    </div>
                </div>
            </div>
        </div>
        """
        
        card = self.generateCard(
            pid=self.getHtmlId("executive_dashboard"),
            html=executive_html,
            cardClass='primary',
            title="<i class='fas fa-tachometer-alt'></i> Executive Dashboard",
            titleBadge='',
            collapse=False,
            noPadding=True
        )
        
        items = [[card, '']]
        return self.generateRowWithCol(12, items, "data-context='executiveDashboard'")
    
    def _build_key_metrics_section(self):
        """Build key metrics section with detailed analytics"""
        if not hasattr(self.data, 'calculate_comprehensive_analytics'):
            return ""
        
        try:
            analytics = self.data.calculate_comprehensive_analytics()
        except Exception as e:
            return f"<div class='alert alert-warning'>Analytics temporarily unavailable: {str(e)}</div>"
        
        financial_metrics = analytics.get('financial_metrics', {})
        roi_analysis = analytics.get('roi_analysis', {})
        
        metrics_html = f"""
        <div class="row">
            <div class="col-md-4">
                <div class="info-box">
                    <span class="info-box-icon bg-success"><i class="fas fa-chart-line"></i></span>
                    <div class="info-box-content">
                        <span class="info-box-text">ROI Potential</span>
                        <span class="info-box-number">{roi_analysis.get('overall_roi_percentage', 0):.0f}%</span>
                        <span class="info-box-more">Annual return on investment</span>
                    </div>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="info-box">
                    <span class="info-box-icon bg-info"><i class="fas fa-stopwatch"></i></span>
                    <div class="info-box-content">
                        <span class="info-box-text">Payback Period</span>
                        <span class="info-box-number">{roi_analysis.get('payback_period_months', 0):.1f}</span>
                        <span class="info-box-more">Months to break even</span>
                    </div>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="info-box">
                    <span class="info-box-icon bg-warning"><i class="fas fa-trophy"></i></span>
                    <div class="info-box-content">
                        <span class="info-box-text">Quick Wins</span>
                        <span class="info-box-number">{financial_metrics.get('quick_wins_count', 0)}</span>
                        <span class="info-box-more">Low-effort, high-impact</span>
                    </div>
                </div>
            </div>
        </div>
        """
        
        card = self.generateCard(
            pid=self.getHtmlId("key_metrics"),
            html=metrics_html,
            cardClass='info',
            title="<i class='fas fa-chart-bar'></i> Key Performance Indicators",
            titleBadge='',
            collapse=True,
            noPadding=False
        )
        
        items = [[card, '']]
        return self.generateRowWithCol(12, items, "data-context='keyMetrics'")
    
    def _build_quick_actions_section(self):
        """Build quick actions section for immediate implementation"""
        if not hasattr(self.data, 'recommendations') or not self.data.recommendations:
            return ""
        
        # Get quick wins (low effort, decent savings)
        quick_wins = [rec for rec in self.data.recommendations 
                     if rec.implementation_effort == 'low' and rec.monthly_savings >= 50][:5]
        
        if not quick_wins:
            return ""
        
        actions_html = """
        <div class="row">
            <div class="col-md-12">
                <p class="text-muted">These recommendations can be implemented quickly with minimal effort:</p>
            </div>
        </div>
        <div class="row">
        """
        
        for rec in quick_wins:
            actions_html += f"""
            <div class="col-md-6 col-lg-4">
                <div class="card card-outline card-success">
                    <div class="card-header">
                        <h5 class="card-title">{rec.service.upper()}</h5>
                        <div class="card-tools">
                            <span class="badge badge-success">${rec.monthly_savings:,.0f}/mo</span>
                        </div>
                    </div>
                    <div class="card-body">
                        <h6>{rec.title}</h6>
                        <p class="text-muted small">{rec.description[:100]}...</p>
                        <div class="d-flex justify-content-between align-items-center">
                            <small class="text-success">
                                <i class="fas fa-clock"></i> {rec.implementation_effort.title()} effort
                            </small>
                            <button class="btn btn-sm btn-success" onclick="showRecommendationDetails('{rec.id}')">
                                Implement
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            """
        
        actions_html += "</div>"
        
        card = self.generateCard(
            pid=self.getHtmlId("quick_actions"),
            html=actions_html,
            cardClass='success',
            title=f"<i class='fas fa-bolt'></i> Quick Wins <span class='badge badge-success'>{len(quick_wins)} available</span>",
            titleBadge='',
            collapse=True,
            noPadding=False
        )
        
        items = [[card, '']]
        return self.generateRowWithCol(12, items, "data-context='quickActions'")
    
    def _build_implementation_roadmap_section(self):
        """Build implementation roadmap section"""
        if not hasattr(self.data, 'executive_summary') or not self.data.executive_summary.implementation_roadmap:
            return ""
        
        roadmap = self.data.executive_summary.implementation_roadmap
        
        roadmap_html = """
        <div class="timeline">
        """
        
        for i, phase in enumerate(roadmap):
            # Determine timeline color based on phase
            color_class = ['success', 'warning', 'info'][i % 3]
            
            roadmap_html += f"""
            <div class="time-label">
                <span class="bg-{color_class}">{phase['timeline']}</span>
            </div>
            <div>
                <i class="fas fa-tasks bg-{color_class}"></i>
                <div class="timeline-item">
                    <span class="time"><i class="fas fa-clock"></i> {phase['timeline']}</span>
                    <h3 class="timeline-header">{phase['phase']}</h3>
                    <div class="timeline-body">
                        <div class="row">
                            <div class="col-md-8">
                                <p><strong>Expected Savings:</strong> ${phase['expected_savings']:,.0f}/month</p>
                                <p><strong>Recommendations:</strong> {phase['recommendation_count']} items</p>
                                <p><strong>Key Activities:</strong></p>
                                <ul>
            """
            
            for activity in phase.get('key_activities', []):
                roadmap_html += f"<li>{activity}</li>"
            
            roadmap_html += f"""
                                </ul>
                            </div>
                            <div class="col-md-4">
                                <div class="progress-group">
                                    <span class="progress-text">Implementation Progress</span>
                                    <span class="float-right"><b>0</b>/100%</span>
                                    <div class="progress progress-sm">
                                        <div class="progress-bar bg-{color_class}" style="width: 0%"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            """
        
        roadmap_html += """
        </div>
        """
        
        card = self.generateCard(
            pid=self.getHtmlId("implementation_roadmap"),
            html=roadmap_html,
            cardClass='primary',
            title=f"<i class='fas fa-road'></i> Implementation Roadmap <span class='badge badge-primary'>{len(roadmap)} phases</span>",
            titleBadge='',
            collapse=True,
            noPadding=False
        )
        
        items = [[card, '']]
        return self.generateRowWithCol(12, items, "data-context='implementationRoadmap'")
    
    def create_recommendation_detail_view(self, recommendation):
        """Create detailed view for a single recommendation"""
        if not recommendation:
            return "<div class='alert alert-warning'>Recommendation not found</div>"
        
        # Security impact assessment
        security_info = ""
        if hasattr(self.data, 'assess_security_impact'):
            try:
                security_assessment = self.data.assess_security_impact([recommendation])
                if security_assessment['high_security_impact']:
                    security_info = """
                    <div class="alert alert-warning">
                        <i class="fas fa-shield-alt"></i> <strong>Security Impact:</strong> 
                        This recommendation has security implications. Review carefully before implementation.
                    </div>
                    """
            except Exception:
                pass  # Security assessment optional
        
        detail_html = f"""
        <div class="row">
            <div class="col-md-8">
                <h4>{recommendation.title}</h4>
                <p class="text-muted">{recommendation.description}</p>
                
                {security_info}
                
                <h5>Implementation Steps</h5>
                <ol>
        """
        
        for step in recommendation.implementation_steps:
            detail_html += f"<li>{step}</li>"
        
        detail_html += f"""
                </ol>
                
                <h5>Required Permissions</h5>
                <ul>
        """
        
        for permission in recommendation.required_permissions:
            detail_html += f"<li><code>{permission}</code></li>"
        
        detail_html += f"""
                </ul>
                
                <h5>Potential Risks</h5>
                <ul class="text-warning">
        """
        
        for risk in recommendation.potential_risks:
            detail_html += f"<li>{risk}</li>"
        
        detail_html += f"""
                </ul>
            </div>
            
            <div class="col-md-4">
                <div class="card card-outline card-info">
                    <div class="card-header">
                        <h5 class="card-title">Recommendation Details</h5>
                    </div>
                    <div class="card-body">
                        <table class="table table-sm">
                            <tr>
                                <td><strong>Service:</strong></td>
                                <td>{recommendation.service.upper()}</td>
                            </tr>
                            <tr>
                                <td><strong>Category:</strong></td>
                                <td>{recommendation.category.title()}</td>
                            </tr>
                            <tr>
                                <td><strong>Source:</strong></td>
                                <td>{recommendation.source.replace('_', ' ').title()}</td>
                            </tr>
                            <tr>
                                <td><strong>Priority:</strong></td>
                                <td><span class="badge badge-{self._get_priority_badge_class(recommendation.priority_level)}">{recommendation.priority_level.title()}</span></td>
                            </tr>
                            <tr>
                                <td><strong>Effort:</strong></td>
                                <td><span class="badge badge-{self._get_effort_badge_class(recommendation.implementation_effort)}">{recommendation.implementation_effort.title()}</span></td>
                            </tr>
                            <tr>
                                <td><strong>Confidence:</strong></td>
                                <td>{recommendation.confidence_level.title()}</td>
                            </tr>
                        </table>
                    </div>
                </div>
                
                <div class="card card-outline card-success mt-3">
                    <div class="card-header">
                        <h5 class="card-title">Financial Impact</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-6">
                                <div class="description-block border-right">
                                    <h5 class="description-header text-success">${recommendation.monthly_savings:,.2f}</h5>
                                    <span class="description-text">Monthly</span>
                                </div>
                            </div>
                            <div class="col-6">
                                <div class="description-block">
                                    <h5 class="description-header text-success">${recommendation.annual_savings:,.2f}</h5>
                                    <span class="description-text">Annual</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card card-outline card-secondary mt-3">
                    <div class="card-header">
                        <h5 class="card-title">Affected Resources</h5>
                    </div>
                    <div class="card-body">
                        <p><strong>Resource Count:</strong> {recommendation.resource_count}</p>
        """
        
        if recommendation.affected_resources:
            detail_html += "<p><strong>Resources:</strong></p><ul class='list-unstyled'>"
            for resource in recommendation.affected_resources[:5]:  # Show first 5
                detail_html += f"<li><small><code>{resource.get('id', 'N/A')}</code> ({resource.get('type', 'Unknown')})</small></li>"
            
            if len(recommendation.affected_resources) > 5:
                detail_html += f"<li><small class='text-muted'>... and {len(recommendation.affected_resources) - 5} more</small></li>"
            
            detail_html += "</ul>"
        
        detail_html += """
                    </div>
                </div>
            </div>
        </div>
        """
        
        return detail_html
    
    def add_interactive_features(self, html_content):
        """Add interactive JavaScript features to the HTML content"""
        interactive_js = """
        <script>
        // Recommendation details modal
        function showRecommendationDetails(recommendationId) {
            // This would typically make an AJAX call to get recommendation details
            // For now, we'll show a placeholder modal
            $('#recommendationModal').modal('show');
            $('#recommendationModalTitle').text('Recommendation Details');
            $('#recommendationModalBody').html('<p>Loading recommendation details for ID: ' + recommendationId + '</p>');
        }
        
        // Expandable table rows
        $(document).ready(function() {
            $('[data-widget="expandable-table"]').click(function() {
                var $this = $(this);
                var $expandableBody = $this.next('.expandable-body');
                
                if ($expandableBody.hasClass('d-none')) {
                    $expandableBody.removeClass('d-none');
                    $this.attr('aria-expanded', 'true');
                } else {
                    $expandableBody.addClass('d-none');
                    $this.attr('aria-expanded', 'false');
                }
            });
            
            // Initialize tooltips
            $('[data-toggle="tooltip"]').tooltip();
            
            // Initialize popovers
            $('[data-toggle="popover"]').popover();
        });
        </script>
        
        <!-- Recommendation Details Modal -->
        <div class="modal fade" id="recommendationModal" tabindex="-1" role="dialog">
            <div class="modal-dialog modal-lg" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="recommendationModalTitle">Recommendation Details</h5>
                        <button type="button" class="close" data-dismiss="modal">
                            <span>&times;</span>
                        </button>
                    </div>
                    <div class="modal-body" id="recommendationModalBody">
                        <!-- Content will be loaded here -->
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary">Implement Recommendation</button>
                    </div>
                </div>
            </div>
        </div>
        """
        
        # Insert before closing body tag
        if '</body>' in html_content:
            html_content = html_content.replace('</body>', f'{interactive_js}</body>')
        else:
            html_content += interactive_js
        
        return html_content
    
    # Task 8.2: Cost Optimization Visualizations
    
    def create_savings_potential_charts(self):
        """Create comprehensive savings potential charts and graphs"""
        if not hasattr(self.data, 'calculate_comprehensive_analytics'):
            return ""
        
        try:
            analytics = self.data.calculate_comprehensive_analytics()
        except Exception as e:
            return f"<div class='alert alert-warning'>Charts temporarily unavailable: {str(e)}</div>"
        
        financial_metrics = analytics.get('financial_metrics', {})
        service_breakdown = analytics.get('service_breakdown', {})
        
        # Savings distribution chart
        savings_distribution = financial_metrics.get('savings_distribution', {})
        distribution_chart = self._create_savings_distribution_chart(savings_distribution)
        
        # Service breakdown chart
        service_chart = self._create_service_breakdown_chart(service_breakdown)
        
        # ROI timeline chart
        roi_analysis = analytics.get('roi_analysis', {})
        roi_chart = self._create_roi_timeline_chart(roi_analysis)
        
        charts_html = f"""
        <div class="row">
            <div class="col-md-6">
                {distribution_chart}
            </div>
            <div class="col-md-6">
                {service_chart}
            </div>
        </div>
        <div class="row mt-3">
            <div class="col-md-12">
                {roi_chart}
            </div>
        </div>
        """
        
        card = self.generateCard(
            pid=self.getHtmlId("savings_charts"),
            html=charts_html,
            cardClass='info',
            title="<i class='fas fa-chart-area'></i> Savings Potential Analysis",
            titleBadge='',
            collapse=True,
            noPadding=False
        )
        
        items = [[card, '']]
        return self.generateRowWithCol(12, items, "data-context='savingsCharts'")
    
    def _create_savings_distribution_chart(self, distribution):
        """Create savings distribution pie chart"""
        if not distribution:
            return "<div class='text-center text-muted'>No distribution data available</div>"
        
        labels = []
        data = []
        colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF']
        
        for i, (range_key, count) in enumerate(distribution.items()):
            if count > 0:
                range_label = {
                    'under_50': 'Under $50/month',
                    '50_to_200': '$50-200/month',
                    '200_to_500': '$200-500/month',
                    '500_to_1000': '$500-1000/month',
                    'over_1000': 'Over $1000/month'
                }.get(range_key, range_key)
                
                labels.append(range_label)
                data.append(count)
        
        chart_id = f"savingsDistChart_{uuid.uuid4().hex[:8]}"
        
        return f"""
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">Savings Distribution</h5>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" width="400" height="300"></canvas>
            </div>
        </div>
        
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            var ctx = document.getElementById('{chart_id}').getContext('2d');
            new Chart(ctx, {{
                type: 'doughnut',
                data: {{
                    labels: {json.dumps(labels)},
                    datasets: [{{
                        data: {json.dumps(data)},
                        backgroundColor: {json.dumps(colors[:len(data)])}
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        legend: {{
                            position: 'bottom'
                        }},
                        title: {{
                            display: true,
                            text: 'Recommendations by Savings Range'
                        }}
                    }}
                }}
            }});
        }});
        </script>
        \"\"\"
    
    def _create_service_breakdown_chart(self, service_breakdown):
        \"\"\"Create service breakdown bar chart\"\"\"
        by_service = service_breakdown.get('by_service', {})
        if not by_service:
            return "<div class='text-center text-muted'>No service data available</div>"
        
        # Sort services by total savings
        sorted_services = sorted(by_service.items(), 
                               key=lambda x: x[1].get('total_savings', 0), reverse=True)[:10]
        
        labels = [service.upper() for service, _ in sorted_services]
        savings_data = [data.get('total_savings', 0) for _, data in sorted_services]
        count_data = [data.get('count', 0) for _, data in sorted_services]
        
        chart_id = f"serviceChart_{uuid.uuid4().hex[:8]}"
        
        return f"""
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">Savings by Service</h5>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" width="400" height="300"></canvas>
            </div>
        </div>
        
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            var ctx = document.getElementById('{chart_id}').getContext('2d');
            new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: {json.dumps(labels)},
                    datasets: [{{
                        label: 'Monthly Savings ($)',
                        data: {json.dumps(savings_data)},
                        backgroundColor: 'rgba(54, 162, 235, 0.8)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1,
                        yAxisID: 'y'
                    }}, {{
                        label: 'Recommendation Count',
                        data: {json.dumps(count_data)},
                        backgroundColor: 'rgba(255, 99, 132, 0.8)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1,
                        type: 'line',
                        yAxisID: 'y1'
                    }}]
                }},
                options: {{
                    responsive: true,
                    interaction: {{
                        mode: 'index',
                        intersect: false,
                    }},
                    scales: {{
                        y: {{
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: {{
                                display: true,
                                text: 'Monthly Savings ($)'
                            }}
                        }},
                        y1: {{
                            type: 'linear',
                            display: true,
                            position: 'right',
                            title: {{
                                display: true,
                                text: 'Recommendation Count'
                            }},
                            grid: {{
                                drawOnChartArea: false,
                            }},
                        }}
                    }}
                }}
            }});
        }});
        </script>
        """
    
    def _create_roi_timeline_chart(self, roi_analysis):
        """Create ROI timeline chart"""
        break_even_timeline = roi_analysis.get('break_even_analysis', [])
        if not break_even_timeline:
            return "<div class='text-center text-muted'>No ROI timeline data available</div>"
        
        labels = [f"After {item['recommendations_implemented']} recs" for item in break_even_timeline]
        cumulative_cost = [item['cumulative_cost'] for item in break_even_timeline]
        monthly_savings = [item['monthly_savings'] for item in break_even_timeline]
        break_even_months = [item['break_even_months'] for item in break_even_timeline]
        
        chart_id = f"roiChart_{uuid.uuid4().hex[:8]}"
        
        return f"""
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">ROI Timeline Analysis</h5>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" width="800" height="400"></canvas>
            </div>
        </div>
        
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            var ctx = document.getElementById('{chart_id}').getContext('2d');
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: {json.dumps(labels)},
                    datasets: [{{
                        label: 'Cumulative Implementation Cost ($)',
                        data: {json.dumps(cumulative_cost)},
                        borderColor: 'rgba(255, 99, 132, 1)',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        yAxisID: 'y'
                    }}, {{
                        label: 'Monthly Savings ($)',
                        data: {json.dumps(monthly_savings)},
                        borderColor: 'rgba(54, 162, 235, 1)',
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        yAxisID: 'y'
                    }}, {{
                        label: 'Break-even Period (months)',
                        data: {json.dumps(break_even_months)},
                        borderColor: 'rgba(75, 192, 192, 1)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        yAxisID: 'y1'
                    }}]
                }},
                options: {{
                    responsive: true,
                    interaction: {{
                        mode: 'index',
                        intersect: false,
                    }},
                    scales: {{
                        y: {{
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: {{
                                display: true,
                                text: 'Cost/Savings ($)'
                            }}
                        }},
                        y1: {{
                            type: 'linear',
                            display: true,
                            position: 'right',
                            title: {{
                                display: true,
                                text: 'Break-even (months)'
                            }},
                            grid: {{
                                drawOnChartArea: false,
                            }},
                        }}
                    }}
                }}
            }});
        }});
        </script>
        \"\"\"
    
    def create_opportunity_matrix_visualization(self):
        \"\"\"Create cost optimization opportunity matrix visualization\"\"\"
        if not hasattr(self.data, 'calculate_comprehensive_analytics'):
            return ""
        
        try:
            analytics = self.data.calculate_comprehensive_analytics()
        except Exception as e:
            return f"<div class='alert alert-warning'>Opportunity matrix temporarily unavailable: {{str(e)}}</div>"
        
        opportunity_matrix = analytics.get('opportunity_matrix', {})
        if not opportunity_matrix:
            return ""
        
        matrix_html = """
        <div class="row">
            <div class="col-md-12">
                <h5>Impact vs Effort Matrix</h5>
                <p class="text-muted">Recommendations plotted by implementation effort and potential impact</p>
            </div>
        </div>
        <div class="row">
        """
        
        # Define matrix layout
        matrix_layout = [
            ['high_impact_low_effort', 'high_impact_medium_effort', 'high_impact_high_effort'],
            ['medium_impact_low_effort', 'medium_impact_medium_effort', 'medium_impact_high_effort'],
            ['low_impact_low_effort', 'low_impact_medium_effort', 'low_impact_high_effort']
        ]
        
        impact_labels = ['High Impact', 'Medium Impact', 'Low Impact']
        effort_labels = ['Low Effort', 'Medium Effort', 'High Effort']
        
        for i, row in enumerate(matrix_layout):
            matrix_html += f"""
            <div class="col-md-12">
                <div class="row mb-2">
                    <div class="col-md-2">
                        <strong>{impact_labels[i]}</strong>
                    </div>
            """
            
            for j, cell_key in enumerate(row):
                cell_data = opportunity_matrix.get(cell_key, [])
                cell_count = len(cell_data)
                
                # Determine cell styling based on desirability
                if i == 0 and j == 0:  # High impact, low effort - most desirable
                    cell_class = 'success'
                elif i == 0:  # High impact
                    cell_class = 'warning'
                elif j == 2:  # High effort
                    cell_class = 'danger'
                else:
                    cell_class = 'info'
                
                matrix_html += f"""
                    <div class="col-md-3">
                        <div class="card card-outline card-{cell_class}">
                            <div class="card-body text-center">
                                <h4 class="text-{cell_class}">{cell_count}</h4>
                                <small class="text-muted">{effort_labels[j]}</small>
                """
                
                # Show top recommendations in this cell
                if cell_data:
                    matrix_html += "<hr><small>"
                    for rec in cell_data[:2]:  # Show top 2
                        matrix_html += f"• {rec['title'][:30]}...<br>"
                    if len(cell_data) > 2:
                        matrix_html += f"... and {len(cell_data) - 2} more"
                    matrix_html += "</small>"
                
                matrix_html += """
                            </div>
                        </div>
                    </div>
                """
            
            matrix_html += """
                </div>
            </div>
            """
        
        matrix_html += """
        </div>
        <div class="row mt-3">
            <div class="col-md-12">
                <div class="alert alert-info">
                    <strong>Matrix Guide:</strong>
                    <span class="badge badge-success ml-2">Green</span> Quick Wins (High Impact, Low Effort)
                    <span class="badge badge-warning ml-2">Yellow</span> Major Projects (High Impact, Higher Effort)
                    <span class="badge badge-danger ml-2">Red</span> Questionable (Low Impact, High Effort)
                </div>
            </div>
        </div>
        """
        
        card = self.generateCard(
            pid=self.getHtmlId("opportunity_matrix"),
            html=matrix_html,
            cardClass='primary',
            title="<i class='fas fa-th'></i> Opportunity Matrix",
            titleBadge='',
            collapse=True,
            noPadding=False
        )
        
        items = [[card, '']]
        return self.generateRowWithCol(12, items, "data-context='opportunityMatrix'")
    
    def create_progress_tracking_charts(self):
        """Create progress tracking and trend charts"""
        if not hasattr(self.data, 'recommendations') or not self.data.recommendations:
            return ""
        
        # Implementation status tracking
        status_counts = {'new': 0, 'reviewed': 0, 'implemented': 0, 'dismissed': 0}
        for rec in self.data.recommendations:
            status_counts[rec.status] = status_counts.get(rec.status, 0) + 1
        
        # Priority progress tracking
        priority_counts = {'high': 0, 'medium': 0, 'low': 0}
        for rec in self.data.recommendations:
            priority_counts[rec.priority_level] = priority_counts.get(rec.priority_level, 0) + 1
        
        progress_html = f"""
        <div class="row">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5 class="card-title">Implementation Progress</h5>
                    </div>
                    <div class="card-body">
                        <canvas id="implementationProgressChart" width="400" height="300"></canvas>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5 class="card-title">Priority Distribution</h5>
                    </div>
                    <div class="card-body">
                        <canvas id="priorityDistributionChart" width="400" height="300"></canvas>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            // Implementation Progress Chart
            var ctx1 = document.getElementById('implementationProgressChart').getContext('2d');
            new Chart(ctx1, {{
                type: 'doughnut',
                data: {{
                    labels: ['New', 'Reviewed', 'Implemented', 'Dismissed'],
                    datasets: [{{
                        data: [{status_counts['new']}, {status_counts['reviewed']}, {status_counts['implemented']}, {status_counts['dismissed']}],
                        backgroundColor: ['#17a2b8', '#ffc107', '#28a745', '#dc3545']
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        legend: {{
                            position: 'bottom'
                        }}
                    }}
                }}
            }});
            
            // Priority Distribution Chart
            var ctx2 = document.getElementById('priorityDistributionChart').getContext('2d');
            new Chart(ctx2, {{
                type: 'bar',
                data: {{
                    labels: ['High Priority', 'Medium Priority', 'Low Priority'],
                    datasets: [{{
                        label: 'Recommendations',
                        data: [{priority_counts['high']}, {priority_counts['medium']}, {priority_counts['low']}],
                        backgroundColor: ['#dc3545', '#ffc107', '#17a2b8']
                    }}]
                }},
                options: {{
                    responsive: true,
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            title: {{
                                display: true,
                                text: 'Number of Recommendations'
                            }}
                        }}
                    }}
                }}
            }});
        }});
        </script>
        """
        
        card = self.generateCard(
            pid=self.getHtmlId("progress_tracking"),
            html=progress_html,
            cardClass='success',
            title="<i class='fas fa-chart-line'></i> Progress Tracking",
            titleBadge='',
            collapse=True,
            noPadding=False
        )
        
        items = [[card, '']]
        return self.generateRowWithCol(12, items, "data-context='progressTracking'")
    
    def create_interactive_recommendation_tables(self):
        """Create interactive recommendation tables with sorting and filtering"""
        if not hasattr(self.data, 'recommendations') or not self.data.recommendations:
            return ""
        
        # Create comprehensive data table
        table_html = """
        <div class="row mb-3">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-header">
                        <div class="row">
                            <div class="col-md-6">
                                <h5 class="card-title">All Recommendations</h5>
                            </div>
                            <div class="col-md-6">
                                <div class="float-right">
                                    <div class="btn-group" role="group">
                                        <button type="button" class="btn btn-sm btn-outline-primary" onclick="filterTable('all')">All</button>
                                        <button type="button" class="btn btn-sm btn-outline-danger" onclick="filterTable('high')">High Priority</button>
                                        <button type="button" class="btn btn-sm btn-outline-warning" onclick="filterTable('medium')">Medium Priority</button>
                                        <button type="button" class="btn btn-sm btn-outline-info" onclick="filterTable('low')">Low Priority</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="card-body">
                        <table id="recommendationsTable" class="table table-bordered table-hover table-striped">
                            <thead class="thead-dark">
                                <tr>
                                    <th>Priority</th>
                                    <th>Service</th>
                                    <th>Title</th>
                                    <th>Monthly Savings</th>
                                    <th>Annual Savings</th>
                                    <th>Effort</th>
                                    <th>Confidence</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
        """
        
        for rec in self.data.recommendations:
            priority_badge = f"<span class='badge badge-{self._get_priority_badge_class(rec.priority_level)}'>{rec.priority_level.title()}</span>"
            effort_badge = f"<span class='badge badge-{self._get_effort_badge_class(rec.implementation_effort)}'>{rec.implementation_effort.title()}</span>"
            status_badge = f"<span class='badge badge-secondary'>{rec.status.title()}</span>"
            
            table_html += f"""
                            <tr data-priority="{rec.priority_level}">
                                <td>{priority_badge}</td>
                                <td>{rec.service.upper()}</td>
                                <td>
                                    <strong>{rec.title}</strong><br>
                                    <small class="text-muted">{rec.description[:80]}...</small>
                                </td>
                                <td>${rec.monthly_savings:,.2f}</td>
                                <td>${rec.annual_savings:,.2f}</td>
                                <td>{effort_badge}</td>
                                <td>{rec.confidence_level.title()}</td>
                                <td>{status_badge}</td>
                                <td>
                                    <div class="btn-group" role="group">
                                        <button class="btn btn-sm btn-outline-primary" onclick="showRecommendationDetails('{rec.id}')" title="View Details">
                                            <i class="fas fa-eye"></i>
                                        </button>
                                        <button class="btn btn-sm btn-outline-success" onclick="implementRecommendation('{rec.id}')" title="Implement">
                                            <i class="fas fa-play"></i>
                                        </button>
                                        <button class="btn btn-sm btn-outline-warning" onclick="reviewRecommendation('{rec.id}')" title="Review">
                                            <i class="fas fa-check"></i>
                                        </button>
                                    </div>
                                </td>
                            </tr>
            """
        
        table_html += """
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
        $(document).ready(function() {
            // Initialize DataTable with advanced features
            $('#recommendationsTable').DataTable({
                "responsive": true,
                "lengthChange": true,
                "autoWidth": false,
                "pageLength": 25,
                "order": [[ 3, "desc" ]], // Sort by monthly savings descending
                "columnDefs": [
                    { "orderable": false, "targets": 8 } // Disable sorting on Actions column
                ],
                "dom": 'Bfrtip',
                "buttons": [
                    'copy', 'csv', 'excel', 'pdf', 'print'
                ]
            });
        });
        
        function filterTable(priority) {
            var table = $('#recommendationsTable').DataTable();
            
            if (priority === 'all') {
                table.search('').columns().search('').draw();
            } else {
                table.column(0).search(priority).draw();
            }
        }
        
        function implementRecommendation(recommendationId) {
            // Implementation logic would go here
            alert('Implementation workflow for recommendation: ' + recommendationId);
        }
        
        function reviewRecommendation(recommendationId) {
            // Review logic would go here
            alert('Review workflow for recommendation: ' + recommendationId);
        }
        </script>
        """
        
        card = self.generateCard(
            pid=self.getHtmlId("interactive_table"),
            html=table_html,
            cardClass='primary',
            title="<i class='fas fa-table'></i> Interactive Recommendations Table",
            titleBadge='',
            collapse=True,
            noPadding=True
        )
        
        items = [[card, '']]
        return self.generateRowWithCol(12, items, "data-context='interactiveTable'")
    
    def add_chart_dependencies(self, html_content):
        """Add Chart.js and DataTables dependencies to HTML content"""
        chart_dependencies = """
        <!-- Chart.js -->
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        
        <!-- DataTables -->
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.11.5/css/dataTables.bootstrap4.min.css">
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/buttons/2.2.2/css/buttons.bootstrap4.min.css">
        <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.11.5/js/jquery.dataTables.min.js"></script>
        <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.11.5/js/dataTables.bootstrap4.min.js"></script>
        <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/buttons/2.2.2/js/dataTables.buttons.min.js"></script>
        <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/buttons/2.2.2/js/buttons.bootstrap4.min.js"></script>
        <script type="text/javascript" charset="utf8" src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.1.3/jszip.min.js"></script>
        <script type="text/javascript" charset="utf8" src="https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.1.53/pdfmake.min.js"></script>
        <script type="text/javascript" charset="utf8" src="https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.1.53/vfs_fonts.js"></script>
        <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/buttons/2.2.2/js/buttons.html5.min.js"></script>
        <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/buttons/2.2.2/js/buttons.print.min.js"></script>
        """
        
        # Insert before closing head tag
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', f'{chart_dependencies}</head>')
        else:
            # If no head tag, add at the beginning
            html_content = chart_dependencies + html_content
        
        return html_content
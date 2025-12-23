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
        """Initialize custom page - simplified for Cloudscape redirect"""
        # No need for Chart.js or DataTables since we're redirecting to Cloudscape UI
        return
    
    def buildContentSummary_customPage(self):
        """Build summary content for the COH page - Cloudscape UI redirect"""
        cloudscape_message = """
        <div class="alert alert-info" role="alert">
            <h4 class="alert-heading"><i class="fas fa-info-circle"></i> Feature Available in Cloudscape UI</h4>
            <p>The Cost Optimization Hub is now available in our modern Cloudscape UI interface, which provides:</p>
            <ul>
                <li>Interactive dashboards and visualizations</li>
                <li>Advanced filtering and sorting capabilities</li>
                <li>Export functionality for recommendations</li>
                <li>Enhanced user experience with modern design</li>
            </ul>
            <hr>
            <p class="mb-0">
                <strong>Please use the Cloudscape UI version for the full Cost Optimization Hub experience.</strong>
            </p>
        </div>
        """
        
        return [cloudscape_message]
    
    def buildContentDetail_customPage(self):
        """Build detailed content for the COH page - Cloudscape UI redirect"""
        return []
    
    def _build_charts_section(self):
        """Build charts section using the framework's chart methods"""
        output = []
        
        if not hasattr(self.data, 'get_recommendations_by_priority'):
            return output
        
        # Get data for charts
        recommendations_by_priority = self.data.get_recommendations_by_priority()
        recommendations_by_category = self.data.get_recommendations_by_category()
        
        items = []
        
        # Priority distribution chart
        priority_data = {}
        for priority, recs in recommendations_by_priority.items():
            priority_data[priority.title()] = len(recs)
        
        if priority_data:
            chart_html = self.generateDonutPieChart(priority_data, 'priority', 'doughnut')
            card = self.generateCard(
                pid=self.getHtmlId('priority_chart'),
                html=chart_html,
                cardClass='primary',
                title='<i class="fas fa-chart-pie"></i> Recommendations by Priority',
                collapse=True
            )
            items.append([card, ''])
        
        # Category distribution chart
        category_data = {}
        for category, recs in recommendations_by_category.items():
            if recs:  # Only include categories with recommendations
                category_data[category.title()] = len(recs)
        
        if category_data:
            chart_html = self.generateDonutPieChart(category_data, 'category', 'pie')
            card = self.generateCard(
                pid=self.getHtmlId('category_chart'),
                html=chart_html,
                cardClass='info',
                title='<i class="fas fa-chart-pie"></i> Recommendations by Category',
                collapse=True
            )
            items.append([card, ''])
        
        if items:
            output.append(self.generateRowWithCol(size=6, items=items, rowHtmlAttr="data-context='charts'"))
        
        return output
    
    def _build_priority_sections(self):
        """Build sections organized by priority level"""
        output = []
        
        if not hasattr(self.data, 'get_recommendations_by_priority'):
            return output
        
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
            table_html = self._create_recommendations_table(recommendations)
            
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
        
        if not hasattr(self.data, 'get_recommendations_by_category'):
            return output
        
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
            
            # Create table for this category
            table_html = self._create_recommendations_table(recommendations)
            
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
    
    def _create_recommendations_table(self, recommendations):
        """Create a table of recommendations using framework patterns"""
        if not recommendations:
            return "<p class='text-muted'>No recommendations available</p>"
        
        # Create table header
        table_html = """
        <div class="table-responsive">
            <table class="table table-bordered table-hover table-striped">
                <thead class="thead-light">
                    <tr>
                        <th>Priority</th>
                        <th>Service</th>
                        <th>Title</th>
                        <th>Monthly Savings</th>
                        <th>Annual Savings</th>
                        <th>Implementation Effort</th>
                        <th>Confidence</th>
                        <th>Resources</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        # Add rows for each recommendation
        for rec in recommendations:
            priority_badge = f"<span class='badge badge-{self._get_priority_badge_class(rec.priority_level)}'>{rec.priority_level.title()}</span>"
            effort_badge = f"<span class='badge badge-{self._get_effort_badge_class(rec.implementation_effort)}'>{rec.implementation_effort.title()}</span>"
            confidence_badge = f"<span class='badge badge-{self._get_confidence_badge_class(rec.confidence_level)}'>{rec.confidence_level.title()}</span>"
            
            table_html += f"""
                <tr>
                    <td>{priority_badge}</td>
                    <td>{rec.service.upper()}</td>
                    <td>
                        <strong>{rec.title}</strong><br>
                        <small class="text-muted">{rec.description[:100]}{'...' if len(rec.description) > 100 else ''}</small>
                    </td>
                    <td>${rec.monthly_savings:,.2f}</td>
                    <td>${rec.annual_savings:,.2f}</td>
                    <td>{effort_badge}</td>
                    <td>{confidence_badge}</td>
                    <td>{rec.resource_count}</td>
                </tr>
            """
        
        table_html += """
                </tbody>
            </table>
        </div>
        """
        
        return table_html
    
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
    
    def _get_confidence_badge_class(self, confidence):
        """Get Bootstrap badge class for confidence level"""
        return {
            'high': 'success',
            'medium': 'warning',
            'low': 'danger'
        }.get(confidence, 'secondary')
    
    def create_savings_potential_charts(self):
        """Create savings potential visualization charts"""
        if not hasattr(self.data, 'recommendations') or not self.data.recommendations:
            return "<p class='text-muted'>No data available for charts</p>"
        
        # Group recommendations by savings ranges
        savings_ranges = {
            'under_100': 0,
            '100_500': 0,
            '500_1000': 0,
            'over_1000': 0
        }
        
        for rec in self.data.recommendations:
            monthly = rec.monthly_savings
            if monthly < 100:
                savings_ranges['under_100'] += 1
            elif monthly < 500:
                savings_ranges['100_500'] += 1
            elif monthly < 1000:
                savings_ranges['500_1000'] += 1
            else:
                savings_ranges['over_1000'] += 1
        
        # Create chart using framework method
        chart_html = self.generateDonutPieChart(savings_ranges, 'savings_potential', 'doughnut')
        
        return chart_html
    
    def create_opportunity_matrix_visualization(self):
        """Create opportunity matrix visualization"""
        if not hasattr(self.data, 'calculate_comprehensive_analytics'):
            return "<p class='text-muted'>Analytics not available</p>"
        
        try:
            analytics = self.data.calculate_comprehensive_analytics()
            opportunity_matrix = analytics.get('opportunity_matrix', {})
            
            if not opportunity_matrix:
                return "<p class='text-muted'>No opportunity matrix data available</p>"
            
            # Create a simple table representation of the matrix
            matrix_html = """
            <div class="table-responsive">
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>Impact/Effort</th>
                            <th>Low Effort</th>
                            <th>Medium Effort</th>
                            <th>High Effort</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for impact in ['high', 'medium', 'low']:
                matrix_html += f"<tr><td><strong>{impact.title()} Impact</strong></td>"
                for effort in ['low', 'medium', 'high']:
                    key = f"{impact}_impact_{effort}_effort"
                    items = opportunity_matrix.get(key, [])
                    count = len(items)
                    total_savings = sum(item.get('monthly_savings', 0) for item in items)
                    matrix_html += f"<td>{count} items<br><small>${total_savings:,.0f}/mo</small></td>"
                matrix_html += "</tr>"
            
            matrix_html += """
                    </tbody>
                </table>
            </div>
            """
            
            return matrix_html
            
        except Exception as e:
            return f"<div class='alert alert-warning'>Opportunity matrix temporarily unavailable: {str(e)}</div>"
    
    def create_progress_tracking_charts(self):
        """Create progress tracking charts"""
        if not hasattr(self.data, 'recommendations') or not self.data.recommendations:
            return "<p class='text-muted'>No progress data available</p>"
        
        # Group by status
        status_counts = {
            'new': 0,
            'reviewed': 0,
            'implemented': 0,
            'dismissed': 0
        }
        
        for rec in self.data.recommendations:
            status = rec.status.lower()
            if status in status_counts:
                status_counts[status] += 1
        
        # Create chart using framework method
        chart_html = self.generateDonutPieChart(status_counts, 'progress_tracking', 'pie')
        
        return chart_html
    
    def create_interactive_recommendation_tables(self):
        """Create interactive recommendation tables"""
        if not hasattr(self.data, 'recommendations') or not self.data.recommendations:
            return "<p class='text-muted'>No recommendations available</p>"
        
        # Add JavaScript for DataTables initialization
        js_code = """
        $(document).ready(function() {
            $('#cohRecommendationsTable').DataTable({
                responsive: true,
                pageLength: 25,
                order: [[3, 'desc']], // Sort by monthly savings descending
                columnDefs: [
                    {
                        targets: [3, 4], // Monthly and annual savings columns
                        render: function(data, type, row) {
                            return type === 'display' ? '$' + parseFloat(data).toLocaleString() : data;
                        }
                    }
                ]
            });
        });
        """
        self.addJS(js_code)
        
        # Create the table
        table_html = """
        <div class="table-responsive">
            <table id="cohRecommendationsTable" class="table table-striped table-bordered">
                <thead>
                    <tr>
                        <th>Priority</th>
                        <th>Service</th>
                        <th>Title</th>
                        <th>Monthly Savings</th>
                        <th>Annual Savings</th>
                        <th>Effort</th>
                        <th>Confidence</th>
                        <th>Resources</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for rec in self.data.recommendations:
            priority_badge = f"<span class='badge badge-{self._get_priority_badge_class(rec.priority_level)}'>{rec.priority_level.title()}</span>"
            effort_badge = f"<span class='badge badge-{self._get_effort_badge_class(rec.implementation_effort)}'>{rec.implementation_effort.title()}</span>"
            confidence_badge = f"<span class='badge badge-{self._get_confidence_badge_class(rec.confidence_level)}'>{rec.confidence_level.title()}</span>"
            
            table_html += f"""
                <tr>
                    <td>{priority_badge}</td>
                    <td>{rec.service.upper()}</td>
                    <td><strong>{rec.title}</strong></td>
                    <td>{rec.monthly_savings}</td>
                    <td>{rec.annual_savings}</td>
                    <td>{effort_badge}</td>
                    <td>{confidence_badge}</td>
                    <td>{rec.resource_count}</td>
                </tr>
            """
        
        table_html += """
                </tbody>
            </table>
        </div>
        """
        
        return table_html
    
    def add_chart_dependencies(self, html_content):
        """Add chart dependencies to HTML content"""
        # This is handled by the framework's addJSLib and addCSSLib methods
        # which are called in customPageInit()
        return html_content
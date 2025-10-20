import { useQuery } from '@tanstack/react-query';
import { companyApi, scoringApi, scrapingApi } from '../lib/api';
import { Building2, TrendingUp, Database, Activity } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function Dashboard() {
  const { data: companies } = useQuery({
    queryKey: ['companies'],
    queryFn: () => companyApi.getAll({ limit: 10 }),
  });

  const { data: stats } = useQuery({
    queryKey: ['scoring-stats'],
    queryFn: () => scoringApi.getStats(),
  });

  const { data: jobs } = useQuery({
    queryKey: ['recent-jobs'],
    queryFn: () => scrapingApi.getJobs({ limit: 5 }),
  });

  const statCards = [
    {
      title: 'Gesamt Firmen',
      value: companies?.data?.total || 0,
      icon: Building2,
      color: 'bg-blue-500',
    },
    {
      title: 'Lead Score Ø',
      value: stats?.data?.average_score?.toFixed(1) || '0',
      icon: TrendingUp,
      color: 'bg-green-500',
    },
    {
      title: 'Aktive Jobs',
      value: jobs?.data?.items?.filter((j) => j.status === 'running').length || 0,
      icon: Activity,
      color: 'bg-purple-500',
    },
    {
      title: 'Datenquellen',
      value: 6,
      icon: Database,
      color: 'bg-orange-500',
    },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-8 py-4">
          <h1 className="text-2xl font-bold text-gray-900">Lead Scraper Dashboard</h1>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-8">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {statCards.map((stat) => (
            <div key={stat.title} className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">{stat.title}</p>
                  <p className="text-3xl font-bold text-gray-900">{stat.value}</p>
                </div>
                <div className={`${stat.color} p-3 rounded-lg`}>
                  <stat.icon className="w-6 h-6 text-white" />
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <Link
            to="/scraping"
            className="bg-gradient-to-r from-blue-500 to-blue-600 rounded-lg shadow-md p-6 text-white hover:from-blue-600 hover:to-blue-700 transition-all"
          >
            <h3 className="text-xl font-semibold mb-2">Neuen Scraping-Job starten</h3>
            <p className="text-blue-100">Stadt/PLZ eingeben und Leads scrapen</p>
          </Link>

          <Link
            to="/companies"
            className="bg-gradient-to-r from-purple-500 to-purple-600 rounded-lg shadow-md p-6 text-white hover:from-purple-600 hover:to-purple-700 transition-all"
          >
            <h3 className="text-xl font-semibold mb-2">Firmen durchsuchen</h3>
            <p className="text-purple-100">Alle gescrapten Firmen anzeigen</p>
          </Link>
        </div>

        {/* Recent Jobs */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">Letzte Scraping Jobs</h2>
          <div className="space-y-3">
            {jobs?.data?.items?.slice(0, 5).map((job) => (
              <div key={job.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900">{job.job_name}</p>
                  <p className="text-sm text-gray-500">
                    {job.city} • {job.industry}
                  </p>
                </div>
                <div className="text-right">
                  <span
                    className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                      job.status === 'completed'
                        ? 'bg-green-100 text-green-800'
                        : job.status === 'running'
                        ? 'bg-blue-100 text-blue-800'
                        : job.status === 'failed'
                        ? 'bg-red-100 text-red-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {job.status}
                  </span>
                  {job.results_count !== undefined && (
                    <p className="text-sm text-gray-500 mt-1">{job.results_count} Ergebnisse</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

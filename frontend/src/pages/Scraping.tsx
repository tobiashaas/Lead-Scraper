import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { scrapingApi } from '../lib/api';
import { Play, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react';

export default function Scraping() {
  const queryClient = useQueryClient();
  const [city, setCity] = useState('');
  const [industry, setIndustry] = useState('');
  const [source, setSource] = useState('11880');
  const [maxPages, setMaxPages] = useState(5);

  const { data: jobs, isLoading } = useQuery({
    queryKey: ['scraping-jobs'],
    queryFn: () => scrapingApi.getJobs({ limit: 50 }),
    refetchInterval: 5000, // Auto-refresh every 5s
  });

  const createJobMutation = useMutation({
    mutationFn: scrapingApi.createJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scraping-jobs'] });
      setCity('');
      setIndustry('');
    },
  });

  const handleStartScraping = (e: React.FormEvent) => {
    e.preventDefault();
    if (!city || !industry) return;

    createJobMutation.mutate({
      source_name: source,
      city,
      industry,
      max_pages: maxPages,
      use_tor: true,
      use_ai: false,
    });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-500" />;
      default:
        return <Clock className="w-5 h-5 text-gray-400" />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Lead Scraping</h1>

        {/* Start Scraping Form */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Neuen Scraping-Job starten</h2>
          <form onSubmit={handleStartScraping} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Stadt / PLZ
                </label>
                <input
                  type="text"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="z.B. Stuttgart oder 70173"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Branche
                </label>
                <input
                  type="text"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  placeholder="z.B. IT, Handwerk, Gastronomie"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Quelle
                </label>
                <select
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="11880">11880.com</option>
                  <option value="gelbe_seiten">Gelbe Seiten</option>
                  <option value="das_oertliche">Das Örtliche</option>
                  <option value="goyellow">GoYellow</option>
                  <option value="unternehmensverzeichnis">Unternehmensverzeichnis</option>
                  <option value="handelsregister">Handelsregister</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max. Seiten
                </label>
                <input
                  type="number"
                  value={maxPages}
                  onChange={(e) => setMaxPages(parseInt(e.target.value))}
                  min="1"
                  max="50"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={createJobMutation.isPending}
              className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              {createJobMutation.isPending ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Wird gestartet...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  Scraping starten
                </>
              )}
            </button>
          </form>
        </div>

        {/* Jobs List */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">Scraping Jobs</h2>
          
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-4 font-medium text-gray-700">Status</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-700">Job Name</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-700">Stadt</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-700">Branche</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-700">Ergebnisse</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-700">Erstellt</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs?.data?.items?.map((job) => (
                    <tr key={job.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          {getStatusIcon(job.status)}
                          <span className="text-sm capitalize">{job.status}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-sm">{job.job_name}</td>
                      <td className="py-3 px-4 text-sm">{job.city}</td>
                      <td className="py-3 px-4 text-sm">{job.industry}</td>
                      <td className="py-3 px-4 text-sm">
                        {job.results_count !== undefined ? (
                          <span className="text-green-600 font-medium">
                            {job.results_count} ({job.new_companies} neu)
                          </span>
                        ) : (
                          '-'
                        )}
                      </td>
                      <td className="py-3 px-4 text-sm text-gray-500">
                        {new Date(job.created_at).toLocaleString('de-DE')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

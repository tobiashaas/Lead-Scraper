import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { companyApi } from '../lib/api';
import { Search, Filter, Loader2 } from 'lucide-react';

export default function Companies() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const limit = 50;

  const { data, isLoading } = useQuery({
    queryKey: ['companies', page, search],
    queryFn: () => companyApi.getAll({ skip: page * limit, limit, search }),
  });

  const getQualityBadge = (quality?: string) => {
    const colors = {
      A: 'bg-green-100 text-green-800',
      B: 'bg-blue-100 text-blue-800',
      C: 'bg-yellow-100 text-yellow-800',
      D: 'bg-orange-100 text-orange-800',
      UNKNOWN: 'bg-gray-100 text-gray-800',
    };
    return colors[quality as keyof typeof colors] || colors.UNKNOWN;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-8 py-4">
          <h1 className="text-2xl font-bold text-gray-900">Firmen</h1>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-8">
        {/* Search Bar */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="flex gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Firmenname, Stadt, Branche suchen..."
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <button className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
              <Filter className="w-5 h-5" />
              Filter
            </button>
          </div>
        </div>

        {/* Companies Table */}
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          {isLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="text-left py-3 px-4 font-medium text-gray-700">Firma</th>
                      <th className="text-left py-3 px-4 font-medium text-gray-700">Stadt</th>
                      <th className="text-left py-3 px-4 font-medium text-gray-700">Branche</th>
                      <th className="text-left py-3 px-4 font-medium text-gray-700">Kontakt</th>
                      <th className="text-left py-3 px-4 font-medium text-gray-700">Lead Quality</th>
                      <th className="text-left py-3 px-4 font-medium text-gray-700">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data?.data?.items?.map((company) => (
                      <tr key={company.id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="py-3 px-4">
                          <div>
                            <p className="font-medium text-gray-900">{company.company_name}</p>
                            {company.website && (
                              <a
                                href={company.website}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm text-blue-600 hover:underline"
                              >
                                {company.website}
                              </a>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4 text-sm">
                          {company.postal_code} {company.city}
                        </td>
                        <td className="py-3 px-4 text-sm">{company.industry || '-'}</td>
                        <td className="py-3 px-4 text-sm">
                          {company.email && <div>{company.email}</div>}
                          {company.phone && <div>{company.phone}</div>}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${getQualityBadge(
                              company.lead_quality
                            )}`}
                          >
                            {company.lead_quality || 'UNKNOWN'}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-sm font-medium">
                          {company.lead_score?.toFixed(1) || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200">
                <div className="text-sm text-gray-700">
                  Zeige {page * limit + 1} - {Math.min((page + 1) * limit, data?.data?.total || 0)} von{' '}
                  {data?.data?.total || 0} Firmen
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(Math.max(0, page - 1))}
                    disabled={page === 0}
                    className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Zurück
                  </button>
                  <button
                    onClick={() => setPage(page + 1)}
                    disabled={(page + 1) * limit >= (data?.data?.total || 0)}
                    className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Weiter
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

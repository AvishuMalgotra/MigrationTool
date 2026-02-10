import { AzureResource } from "@/lib/api";

interface InventoryTableProps {
    resources: AzureResource[];
    blockers: Record<string, string[]>;
}

export default function InventoryTable({ resources, blockers }: InventoryTableProps) {
    return (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 bg-gray-50 flex justify-between">
                <h3 className="text-lg font-medium text-gray-900">Resource Inventory</h3>
                <span className="text-sm text-gray-500">Showing {resources.length} items</span>
            </div>
            <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Can be moved</th>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Resource Type</th>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Resource Group</th>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Location</th>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subscription</th>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Remarks</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {resources.map((res) => {
                            const blockersList = blockers[res.id] || [];
                            const isBlocked = blockersList.length > 0;
                            const combinedIssues = blockersList.join(" ").toLowerCase();
                            const subId = res.id.split("/")[2] || "unknown";
                            const isUnknown = combinedIssues.includes("no specific official documentation");

                            const getHumanType = (t: string) => {
                                const parts = t.split("/");
                                const last = parts[parts.length - 1];
                                return last ? last.charAt(0).toUpperCase() + last.slice(1) : t;
                            };

                            const getRemarks = () => {
                                if (isBlocked) {
                                    if (isUnknown) return "";
                                    return "This resource type does not support move operation and will be recreated in the Destination Subscription with same configurations.";
                                }
                                return "This resource type supports for direct move operation.";
                            };

                            const renderStatus = () => {
                                if (isBlocked) {
                                    if (isUnknown) return <span className="text-gray-400">-</span>;
                                    return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">No</span>;
                                }
                                return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Yes</span>;
                            };

                            return (
                                <tr key={res.id} className="hover:bg-gray-50">
                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{res.name}</td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{getHumanType(res.type)}</td>
                                    <td className="px-6 py-4 whitespace-nowrap">{renderStatus()}</td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400 font-mono text-xs">{res.type}</td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{res.resource_group}</td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{res.location}</td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-mono text-xs">{subId}</td>
                                    <td className="px-6 py-4 text-sm text-gray-500 max-w-md truncate" title={getRemarks()}>{getRemarks()}</td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
